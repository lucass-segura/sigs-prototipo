"""Modelo de datos del prototipo SIGS.

Las tablas y los campos siguen los diagramas de `docs/referencias/der-*.png`.
Los campos técnicos extra se documentan junto a cada modelo.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .normalizacion import normalizar_identificador_bien, normalizar_identificador_persona


class RegistroInmutable(Exception):
    """Se intentó modificar o borrar un registro que solo admite altas."""


class SoloAltasQuerySet(models.QuerySet):
    """QuerySet que impide actualizar y borrar en bloque."""

    def update(self, **kwargs):
        raise RegistroInmutable("Este registro solo admite altas: no se puede modificar.")

    def delete(self):
        raise RegistroInmutable("Este registro solo admite altas: no se puede borrar.")


class SoloAltasModel(models.Model):
    """Base de las tablas que nunca se editan ni se borran."""

    objects = SoloAltasQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroInmutable(f"{self._meta.db_table}: un registro existente no se puede modificar.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutable(f"{self._meta.db_table}: un registro no se puede borrar.")


# --------------------------------------------------------------------------
# Espacios y usuarios
# --------------------------------------------------------------------------
class EspacioTrabajo(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    creado_en = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "espacio_trabajo"

    def __str__(self):
        return self.nombre


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, nombre, rol, espacio=None, password=None, **extra):
        usuario = self.model(email=self.normalize_email(email).lower(), nombre=nombre, rol=rol, espacio=espacio, **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save()
        return usuario


class Usuario(AbstractBaseUser):
    PERITO = "perito"
    ADMINISTRADOR = "administrador"
    SUPERADMINISTRADOR = "superadministrador"
    ROLES = [(PERITO, "Perito"), (ADMINISTRADOR, "Administrador del espacio"), (SUPERADMINISTRADOR, "Superadministrador")]

    espacio = models.ForeignKey(EspacioTrabajo, null=True, blank=True, on_delete=models.PROTECT, related_name="usuarios")
    nombre = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    rol = models.CharField(max_length=20, choices=ROLES)
    activo = models.BooleanField(default=True)
    contacto_email = models.EmailField(blank=True, default="")
    contacto_visible = models.BooleanField(default=False)
    # Extras técnicos (bloqueo por intentos fallidos)
    intentos_fallidos = models.PositiveIntegerField(default=0)
    bloqueado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombre", "rol"]
    objects = UsuarioManager()

    class Meta:
        db_table = "usuario"
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(rol="superadministrador", espacio__isnull=True)
                    | (~Q(rol="superadministrador") & Q(espacio__isnull=False))
                ),
                name="usuario_espacio_nulo_solo_superadmin",
            )
        ]

    @property
    def is_active(self):
        return self.activo

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nombre} <{self.email}>"


# --------------------------------------------------------------------------
# Expediente
# --------------------------------------------------------------------------
class Poliza(models.Model):
    numero = models.CharField(max_length=60)
    compania = models.CharField(max_length=150, blank=True, default="")
    cobertura = models.CharField(max_length=150, blank=True, default="")
    inicio_vigencia = models.DateField(null=True, blank=True)
    primer_pago = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "poliza"


class Persona(models.Model):
    DNI, CUIT, PASAPORTE = "DNI", "CUIT", "PASAPORTE"
    TIPOS = [(DNI, "DNI"), (CUIT, "CUIT"), (PASAPORTE, "Pasaporte")]

    identificador = models.CharField(max_length=40)
    tipo_identificador = models.CharField(max_length=10, choices=TIPOS, default=DNI)
    nombre = models.CharField(max_length=150)

    class Meta:
        db_table = "persona"
        constraints = [
            models.UniqueConstraint(fields=["tipo_identificador", "identificador"], name="persona_unica_por_identificador")
        ]

    def save(self, *args, **kwargs):
        self.identificador = normalizar_identificador_persona(self.identificador)
        super().save(*args, **kwargs)


class Bien(models.Model):
    TIPOS = [
        ("vehiculo", "Vehículo"),
        ("motocicleta", "Motocicleta"),
        ("telefono", "Teléfono"),
        ("computadora", "Computadora"),
        ("otro", "Otro"),
    ]
    # Solo estos bienes se identifican con un dato único (la patente) y cruzan entre casos (S23). Los demás
    # se registran en el caso con su identificador y su descripción, pero nunca cruzan.
    TIPOS_IDENTIFICABLES = ("vehiculo", "motocicleta")

    tipo = models.CharField(max_length=20, choices=TIPOS)
    identificador_norm = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField(max_length=250, blank=True, default="")
    atributos = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "bien"

    def __init__(self, *args, identificador=None, **kwargs):
        super().__init__(*args, **kwargs)
        if identificador is not None:
            self.identificador_norm = normalizar_identificador_bien(identificador)

    def save(self, *args, **kwargs):
        self.identificador_norm = normalizar_identificador_bien(self.identificador_norm)
        super().save(*args, **kwargs)


class Siniestro(models.Model):
    BORRADOR, EN_ANALISIS, CERRADO, ARCHIVADO, ANULADO = "borrador", "en_analisis", "cerrado", "archivado", "anulado"
    ESTADOS = [
        (BORRADOR, "Borrador"),
        (EN_ANALISIS, "En análisis"),
        (CERRADO, "Cerrado"),
        (ARCHIVADO, "Archivado"),
        (ANULADO, "Anulado"),
    ]
    ESTADOS_VALIDOS_COMO_ANTECEDENTE = (EN_ANALISIS, CERRADO, ARCHIVADO)

    espacio = models.ForeignKey(EspacioTrabajo, on_delete=models.PROTECT, related_name="siniestros")
    perito = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="siniestros")
    poliza = models.ForeignKey(Poliza, null=True, blank=True, on_delete=models.PROTECT, related_name="siniestros")
    numero_expediente = models.CharField(max_length=40, unique=True)
    tipo = models.CharField(max_length=150, blank=True, default="")
    fecha_hecho = models.DateTimeField()
    fecha_denuncia = models.DateField(null=True, blank=True)
    lugar = models.CharField(max_length=250, blank=True, default="")
    relato = models.TextField(blank=True, default="")
    estado = models.CharField(max_length=15, choices=ESTADOS, default=BORRADOR)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    # Extras técnicos
    motivo_anulacion = models.TextField(blank=True, default="")
    # Datos de la denuncia del Anexo 1 del Entregable 4 que el diagrama no tiene (S24). `fecha_denuncia` sigue
    # siendo una fecha: R08 no usa la hora.
    numero_denuncia = models.CharField(max_length=60, blank=True, default="")
    hora_denuncia = models.TimeField(null=True, blank=True)
    asesor = models.CharField(max_length=100, blank=True, default="")
    intervenciones = models.CharField(max_length=250, blank=True, default="")
    documentacion_adjunta = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(default=timezone.now)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "siniestro"
        indexes = [models.Index(fields=["estado", "confirmado_en"], name="siniestro_estado_confirmado")]

    def __str__(self):
        return self.numero_expediente


class Participacion(models.Model):
    ROLES = [("asegurado", "Asegurado"), ("conductor", "Conductor"), ("tercero", "Tercero"), ("testigo", "Testigo")]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name="participaciones")
    persona = models.ForeignKey(Persona, on_delete=models.PROTECT, related_name="participaciones")
    rol = models.CharField(max_length=15, choices=ROLES)
    # Extra técnico: el nombre es del caso (como lo declaró el perito), no de la persona. Persona.nombre
    # no se devuelve a ningún cliente.
    nombre = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        db_table = "participacion"
        constraints = [models.UniqueConstraint(fields=["siniestro", "persona", "rol"], name="participacion_unica")]
        indexes = [
            models.Index(fields=["persona"], name="participacion_persona_idx"),
            models.Index(fields=["siniestro"], name="participacion_siniestro_idx"),
        ]


class BienAfectado(models.Model):
    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name="bienes_afectados")
    bien = models.ForeignKey(Bien, on_delete=models.PROTECT, related_name="afectaciones")
    detalle_dano = models.TextField(blank=True, default="")
    # Extras técnicos: descripción y atributos del bien tal como los declaró este caso. Los de `Bien`
    # no se devuelven a ningún cliente.
    descripcion = models.CharField(max_length=250, blank=True, default="")
    atributos = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "bien_afectado"
        constraints = [models.UniqueConstraint(fields=["siniestro", "bien"], name="bien_afectado_unico")]
        indexes = [
            models.Index(fields=["bien"], name="bien_afectado_bien_idx"),
            models.Index(fields=["siniestro"], name="bien_afectado_siniestro_idx"),
        ]


class Documento(models.Model):
    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name="documentos")
    tipo = models.CharField(max_length=60)
    archivo_ref = models.CharField(max_length=250)
    estado = models.CharField(max_length=20, default="recibido")
    recibido_en = models.DateTimeField(default=timezone.now)
    # Extras técnicos
    nombre_original = models.CharField(max_length=250, blank=True, default="")
    tipo_contenido = models.CharField(max_length=120, blank=True, default="")
    tamanio = models.BigIntegerField(default=0)
    subido_por = models.ForeignKey(Usuario, null=True, on_delete=models.PROTECT, related_name="documentos_subidos")

    class Meta:
        db_table = "documento"


class Nota(models.Model):
    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name="notas")
    autor = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="notas")
    texto = models.TextField()
    creada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "nota"


class Tarea(models.Model):
    PENDIENTE, EN_CURSO, HECHA = "pendiente", "en_curso", "hecha"
    ESTADOS = [(PENDIENTE, "Pendiente"), (EN_CURSO, "En curso"), (HECHA, "Hecha")]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.CASCADE, related_name="tareas")
    titulo = models.CharField(max_length=250)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=PENDIENTE)
    vence_en = models.DateField(null=True, blank=True)
    creada_en = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tarea"


class TareaCambio(models.Model):
    """Historial de cambios de estado de una tarea."""

    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE, related_name="cambios")
    estado_anterior = models.CharField(max_length=10, blank=True, default="")
    estado_nuevo = models.CharField(max_length=10)
    usuario = models.ForeignKey(Usuario, on_delete=models.PROTECT)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "tarea_cambio"
        ordering = ["fecha", "id"]


class Cierre(SoloAltasModel):
    APROBADO, RECHAZADO, DESISTIDO, OTRA = "aprobado", "rechazado", "desistido", "otra_finalizacion"
    RESULTADOS = [
        (APROBADO, "Aprobado"),
        (RECHAZADO, "Rechazado"),
        (DESISTIDO, "Desistido"),
        (OTRA, "Otra finalización"),
    ]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.PROTECT, related_name="cierres")
    perito = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="cierres")
    resultado_reclamo = models.CharField(max_length=20, choices=RESULTADOS)
    irregularidad = models.BooleanField(default=False)
    conclusion = models.TextField(blank=True, default="")
    valoracion = models.PositiveSmallIntegerField()
    justificacion = models.CharField(max_length=500)
    creado_en = models.DateTimeField(default=timezone.now)
    motivo_cambio = models.TextField(blank=True, default="")
    # Respaldo de la irregularidad confirmada (S18): ids de documentos del mismo expediente y/o una observación.
    # Los exige la API cuando `irregularidad` es verdadera. No salen del expediente: el resumen no los muestra.
    documentos_respaldo = models.JSONField(default=list, blank=True)
    observacion_respaldo = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        db_table = "cierre"
        constraints = [
            models.CheckConstraint(condition=Q(valoracion__gte=1, valoracion__lte=10), name="cierre_valoracion_1_a_10"),
            models.CheckConstraint(condition=Q(justificacion__regex=r"\S"), name="cierre_justificacion_no_vacia"),
        ]
        indexes = [models.Index(fields=["siniestro", "creado_en"], name="cierre_siniestro_fecha_idx")]


# --------------------------------------------------------------------------
# Reglas y evaluaciones
# --------------------------------------------------------------------------
class ConjuntoReglas(models.Model):
    version = models.CharField(max_length=20, unique=True)
    vigente_desde = models.DateField()
    topes = models.JSONField(default=dict)
    activo = models.BooleanField(default=False)
    # Extras técnicos
    creado_en = models.DateTimeField(default=timezone.now)
    creado_por = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    basado_en = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="derivados")

    class Meta:
        db_table = "conjunto_reglas"
        constraints = [
            models.UniqueConstraint(fields=["activo"], condition=Q(activo=True), name="un_solo_conjunto_activo")
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            campos = kwargs.get("update_fields")
            if campos is None or set(campos) != {"activo"}:
                raise RegistroInmutable("Un conjunto de reglas publicado solo puede cambiar el campo `activo`.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutable("Un conjunto de reglas no se puede borrar.")

    def __str__(self):
        return self.version


class Regla(models.Model):
    conjunto = models.ForeignKey(ConjuntoReglas, on_delete=models.PROTECT, related_name="reglas")
    codigo = models.CharField(max_length=5)
    nombre = models.CharField(max_length=150)
    grupo = models.CharField(max_length=30)
    parametros = models.JSONField(default=dict)
    puntos_max = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "regla"
        ordering = ["codigo"]
        constraints = [models.UniqueConstraint(fields=["conjunto", "codigo"], name="regla_unica_por_conjunto")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RegistroInmutable("Una regla publicada no se edita: hay que crear una versión nueva.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RegistroInmutable("Una regla no se puede borrar.")


class Evaluacion(SoloAltasModel):
    BAJA, MEDIA, ALTA = "baja", "media", "alta"
    PRIORIDADES = [(BAJA, "Baja"), (MEDIA, "Media"), (ALTA, "Alta")]
    MOTIVOS = [
        ("confirmacion", "Confirmación"),
        ("recalculo", "Recálculo"),
        ("antecedente_confirmado", "Antecedente confirmado"),
        ("antecedente_cerrado", "Antecedente cerrado o con cierre modificado"),
        ("antecedente_archivado", "Antecedente archivado"),
        ("antecedente_anulado", "Antecedente anulado"),
        ("nueva_version", "Nueva versión de reglas"),
        ("escenario", "Escenario de prueba"),
    ]

    siniestro = models.ForeignKey(Siniestro, on_delete=models.PROTECT, related_name="evaluaciones")
    conjunto = models.ForeignKey(ConjuntoReglas, on_delete=models.PROTECT, related_name="evaluaciones")
    puntaje = models.PositiveSmallIntegerField()
    prioridad = models.CharField(max_length=10, choices=PRIORIDADES)
    entradas = models.JSONField(default=dict)
    creada_en = models.DateTimeField(default=timezone.now)
    motivo = models.CharField(max_length=30, choices=MOTIVOS, default="confirmacion")

    class Meta:
        db_table = "evaluacion"
        indexes = [models.Index(fields=["siniestro", "creada_en"], name="evaluacion_siniestro_fecha_idx")]


class Senal(SoloAltasModel):
    ACTIVADA, NO_ACTIVADA, NO_EVALUABLE = "activada", "no_activada", "no_evaluable"
    ESTADOS = [(ACTIVADA, "Activada"), (NO_ACTIVADA, "No activada"), (NO_EVALUABLE, "No evaluable")]

    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.PROTECT, related_name="senales")
    regla = models.ForeignKey(Regla, on_delete=models.PROTECT, related_name="senales")
    estado = models.CharField(max_length=15, choices=ESTADOS)
    puntos = models.PositiveSmallIntegerField(default=0)
    antecedentes = models.JSONField(default=list)
    texto_explicacion = models.TextField(blank=True, default="")
    dato = models.JSONField(default=dict)

    class Meta:
        db_table = "senal"
        ordering = ["regla__codigo"]


# --------------------------------------------------------------------------
# Auditoría
# --------------------------------------------------------------------------
class Auditoria(SoloAltasModel):
    PERMITIDO, RECHAZADO = "permitido", "rechazado"
    RESULTADOS = [(PERMITIDO, "Permitido"), (RECHAZADO, "Rechazado")]

    usuario = models.ForeignKey(Usuario, null=True, blank=True, on_delete=models.PROTECT, related_name="auditorias")
    siniestro_origen = models.ForeignKey(Siniestro, null=True, blank=True, on_delete=models.PROTECT, related_name="auditorias")
    accion = models.CharField(max_length=120)
    objeto = models.CharField(max_length=250, blank=True, default="")
    resultado = models.CharField(max_length=10, choices=RESULTADOS)
    fecha = models.DateTimeField(auto_now_add=True)
    # Extras técnicos: espacio para filtrar y detalle libre
    espacio = models.ForeignKey(EspacioTrabajo, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    detalle = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "auditoria"
        indexes = [models.Index(fields=["espacio", "fecha"], name="auditoria_espacio_fecha_idx")]
        ordering = ["-fecha", "-id"]
