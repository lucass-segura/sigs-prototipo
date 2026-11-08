"""Datos de demostración (todo ficticio): la narrativa del TFG sobre dos espacios de trabajo."""
import uuid
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

from .constantes import CLAVE_DEMO
from .fabrica import crear_siniestro
from .models import Documento, EspacioTrabajo, Nota, Siniestro, Tarea, TareaCambio, Usuario
from .motor import guardar_evaluacion

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
NORTE = "Estudio Pericial Norte"
SUR = "Perito Independiente Sur"


def _momento(anio, mes, dia, hora=12, minuto=0):
    return datetime(anio, mes, dia, hora, minuto, tzinfo=ZONA)


def _persona(identificador, nombre, *roles):
    return {"tipo_identificador": "DNI", "identificador": identificador, "nombre": nombre, "roles": list(roles)}


def _poliza(numero, vigencia, pago):
    return {"numero": numero, "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo", "inicio_vigencia": vigencia, "primer_pago": pago}


def hay_demo():
    return Usuario.objects.filter(email="superadmin@sigs.test").exists()


def _usuarios():
    validate_password(CLAVE_DEMO)  # la contraseña de la demo cumple la política
    norte = EspacioTrabajo.objects.create(nombre=NORTE)
    sur = EspacioTrabajo.objects.create(nombre=SUR)

    def crear(email, nombre, rol, espacio, **extra):
        return Usuario.objects.create_user(email=email, nombre=nombre, rol=rol, espacio=espacio, password=CLAVE_DEMO, **extra)

    return {
        "superadmin": crear("superadmin@sigs.test", "Superadministrador", Usuario.SUPERADMINISTRADOR, None),
        "admin_norte": crear("admin.norte@sigs.test", "Admin Norte", Usuario.ADMINISTRADOR, norte),
        "admin_sur": crear("admin.sur@sigs.test", "Admin Sur", Usuario.ADMINISTRADOR, sur),
        "pe08": crear("perito08@sigs.test", "PE-08", Usuario.PERITO, norte, contacto_email="pe08@correo.test", contacto_visible=True),
        "pe11": crear("perito11@sigs.test", "PE-11", Usuario.PERITO, norte, contacto_visible=False),
        "pe15": crear("perito15@sigs.test", "PE-15", Usuario.PERITO, sur, contacto_email="pe15@correo.test", contacto_visible=True),
    }


def _cierre(resultado, valoracion, justificacion, creado_en, irregularidad=False, conclusion=""):
    return {"resultado_reclamo": resultado, "irregularidad": irregularidad, "valoracion": valoracion,
            "justificacion": justificacion, "conclusion": conclusion, "creado_en": creado_en}


def _guardar_documento(caso, perito):
    """Un documento de texto ficticio en el volumen privado."""
    carpeta = Path(settings.DOCUMENTOS_DIR) / str(caso.pk)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = uuid.uuid4().hex
    contenido = (
        "Acta de inspección (documento ficticio).\n"
        "Vehículo AB123CD con daños por incendio. Numeración de motor y chasis coincide con la cédula.\n"
    ).encode()
    (carpeta / nombre).write_bytes(contenido)
    Documento.objects.create(
        siniestro=caso, tipo="Acta de inspección", archivo_ref=f"{caso.pk}/{nombre}", estado="recibido",
        recibido_en=_momento(2026, 8, 19, 16, 30), nombre_original="acta-inspeccion.txt", tipo_contenido="text/plain",
        tamanio=len(contenido), subido_por=perito,
    )


def _seguimiento_del_caso_0147(caso, perito):
    def tarea(titulo, estado, vence=None, creada=(2026, 8, 18), cambios=()):
        t = Tarea.objects.create(siniestro=caso, titulo=titulo, estado=estado, vence_en=vence, creada_en=_momento(*creada, 11))
        for anterior, nuevo, cuando in cambios:
            TareaCambio.objects.create(tarea=t, estado_anterior=anterior, estado_nuevo=nuevo, usuario=perito, fecha=cuando)

    tarea("Pedir resultado del antecedente S-2025-0381", Tarea.PENDIENTE, date(2026, 8, 27))
    tarea("Redactar informe", Tarea.PENDIENTE, date(2026, 9, 1))
    tarea("Esperar acta policial", Tarea.EN_CURSO, None, (2026, 8, 16),
          [("pendiente", "en_curso", _momento(2026, 8, 18, 12))])
    tarea("Inspección del vehículo", Tarea.HECHA, None, (2026, 8, 18),
          [("pendiente", "en_curso", _momento(2026, 8, 18, 15)), ("en_curso", "hecha", _momento(2026, 8, 19, 17))])
    tarea("Entrevista al asegurado", Tarea.HECHA, None, (2026, 8, 18), [("pendiente", "hecha", _momento(2026, 8, 21, 10))])
    for dia, hora, texto in (
        (18, 11, "Recibo el caso. Falta foto del número de chasis."),
        (19, 17, "Numeración de motor y chasis coincide con la cédula. Habitáculo y motor quemados por completo."),
        (21, 10, "El asegurado amplía el relato. Dice que el auto no tenía fallas previas."),
    ):
        Nota.objects.create(siniestro=caso, autor=perito, texto=texto, creada_en=_momento(2026, 8, dia, hora))
    _guardar_documento(caso, perito)


@transaction.atomic
def cargar_demo():
    """Crea espacios, usuarios y casos, y evalúa cada caso confirmado cuando toda la red ya está cargada."""
    u = _usuarios()
    confirmados = []

    def caso(perito, numero, **campos):
        s = crear_siniestro(u[perito], numero, **campos)
        if s.estado in (Siniestro.EN_ANALISIS, Siniestro.CERRADO, Siniestro.ARCHIVADO) or s.confirmado_en:
            confirmados.append(s)
        return s

    p17 = _persona("30111017", "P-17", "asegurado", "conductor")

    # Incendio total (Norte, PE-08): R01 25, R02 20 y R06 25 → 55, alta
    exp_0147 = caso(
        "pe08", "EXP-2026-0147", tipo="Incendio total", fecha_hecho=_momento(2026, 8, 12, 23, 40), fecha_denuncia=date(2026, 8, 14),
        lugar="Vía pública, Neuquén", relato="El asegurado informa que el vehículo se incendió estacionado en la vía pública. (Relato ficticio.)",
        poliza=_poliza("AUT-000123", date(2026, 7, 20), date(2026, 8, 4)), personas=[p17],
        bienes=[{"tipo": "vehiculo", "identificador": "AB123CD", "descripcion": "Automóvil sedán (ficticio)",
                 "detalle_dano": "Habitáculo y motor quemados por completo.",
                 "atributos": {"motor": "MTR-4471-X", "chasis": "CHS-98213-K", "marca": "Marca Ejemplo"}}],
        confirmado_en=_momento(2026, 8, 18, 10, 42),
    )
    _seguimiento_del_caso_0147(exp_0147, u["pe08"])

    # Antecedente del mismo vehículo en el otro espacio (Sur, PE-15): aprobado, valoración 7
    caso(
        "pe15", "S-2025-0381", tipo="Robo parcial de vehículo", fecha_hecho=_momento(2025, 7, 10, 15, 0), fecha_denuncia=date(2025, 7, 11),
        lugar="Estacionamiento, Cipolletti", relato="Robo de partes del vehículo (relato ficticio del antecedente).",
        poliza=_poliza("AUT-000458", date(2024, 3, 1), date(2024, 3, 5)), personas=[_persona("20222052", "P-52", "asegurado")],
        bienes=[{"tipo": "vehiculo", "identificador": "AB123CD", "descripcion": "Automóvil sedán (ficticio)", "detalle_dano": "Faltan ópticas y llantas."}],
        estado=Siniestro.CERRADO, confirmado_en=_momento(2025, 7, 12, 9, 0),
        cierre=_cierre("aprobado", 7, "Faltó la denuncia policial original. El resto de la documentación coincide.",
                       _momento(2025, 8, 20, 12), conclusion="Hecho verificado con observaciones menores."),
    )

    # Robo de rueda de auxilio: el mismo dominio repetido en los dos espacios
    caso("pe08", "EXP-2026-0160", tipo="Robo de rueda de auxilio", fecha_hecho=_momento(2026, 8, 5, 8, 30), fecha_denuncia=date(2026, 8, 6),
         lugar="Playa de estacionamiento, Neuquén", poliza=_poliza("AUT-000771", date(2025, 1, 10), date(2025, 1, 12)),
         personas=[_persona("28444040", "P-40", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AD555RR", "detalle_dano": "Rueda de auxilio sustraída."}])
    caso("pe15", "S-2025-0410", tipo="Robo de rueda de auxilio", fecha_hecho=_momento(2025, 11, 20, 19, 0), fecha_denuncia=date(2025, 11, 21),
         poliza=_poliza("AUT-000772", date(2024, 6, 1), date(2024, 6, 3)), personas=[_persona("29555041", "P-41", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AD555RR", "detalle_dano": "Rueda de auxilio sustraída."}],
         estado=Siniestro.CERRADO, cierre=_cierre("aprobado", 8, "Documentación completa y denuncia policial coincidente.", _momento(2025, 12, 15, 12)))
    caso("pe15", "S-2026-0030", tipo="Robo de rueda de auxilio", fecha_hecho=_momento(2026, 3, 15, 21, 15), fecha_denuncia=date(2026, 3, 16),
         poliza=_poliza("AUT-000773", date(2024, 6, 1), date(2024, 6, 3)), personas=[_persona("30666042", "P-42", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AD555RR", "detalle_dano": "Rueda de auxilio sustraída."}],
         estado=Siniestro.CERRADO,
         cierre=_cierre("desistido", 5, "El asegurado desistió antes de presentar la denuncia policial.", _momento(2026, 4, 10, 12)))
    caso("pe11", "EXP-2026-0098", tipo="Robo de rueda de auxilio", fecha_hecho=_momento(2026, 7, 2, 7, 45), fecha_denuncia=date(2026, 7, 3),
         poliza=_poliza("AUT-000774", date(2025, 2, 1), date(2025, 2, 3)), personas=[_persona("31777043", "P-43", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AD555RR", "detalle_dano": "Rueda de auxilio sustraída."}])

    # R07: la persona P-31 figura en un antecedente cerrado con irregularidad confirmada
    p31 = _persona("27333031", "P-31", "asegurado", "conductor")
    caso("pe08", "EXP-2026-0139", tipo="Choque en calle", fecha_hecho=_momento(2026, 8, 2, 18, 20), fecha_denuncia=date(2026, 8, 3),
         lugar="Calle San Martín, Neuquén", poliza=_poliza("AUT-000530", date(2025, 4, 1), date(2025, 4, 3)), personas=[p31],
         bienes=[{"tipo": "vehiculo", "identificador": "AC904KL", "detalle_dano": "Daños en el frente."}])
    caso("pe15", "S-2024-0207", tipo="Choque con lesiones", fecha_hecho=_momento(2024, 3, 10, 14, 0), fecha_denuncia=date(2024, 3, 11),
         poliza=_poliza("AUT-000201", date(2023, 1, 1), date(2023, 1, 3)), personas=[_persona("27333031", "P-31", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AE777ZZ"}], estado=Siniestro.CERRADO,
         cierre=_cierre("rechazado", 2, "Se confirmó la adulteración de la documentación presentada.", _momento(2024, 5, 20, 12),
                        irregularidad=True, conclusion="Irregularidad confirmada."))

    # Anulado por carga errónea: comparte el vehículo con EXP-2026-0139 y no tiene que aparecer como antecedente
    caso("pe11", "EXP-2026-0120", tipo="Choque en calle", fecha_hecho=_momento(2026, 6, 20, 10, 0), fecha_denuncia=date(2026, 6, 21),
         poliza=_poliza("AUT-000530", date(2025, 4, 1), date(2025, 4, 3)), personas=[_persona("32888044", "P-44", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AC904KL"}], estado=Siniestro.ANULADO,
         motivo_anulacion="Carga errónea: se cargó con el vehículo de otro asegurado.")

    # Sin coincidencias, más un borrador
    caso("pe08", "EXP-2026-0151", tipo="Robo de celular", fecha_hecho=_momento(2026, 8, 15, 20, 10), fecha_denuncia=date(2026, 8, 16),
         poliza=_poliza("CEL-000310", date(2025, 8, 1), date(2025, 8, 3)), personas=[_persona("33999045", "P-45", "asegurado")],
         bienes=[{"tipo": "telefono", "identificador": "357000000004471", "descripcion": "Teléfono (ficticio)"}])
    caso("pe08", "EXP-2026-0122", tipo="Daño por granizo", fecha_hecho=_momento(2026, 7, 18, 16, 0), fecha_denuncia=date(2026, 7, 19),
         poliza=_poliza("AUT-000615", date(2025, 3, 1), date(2025, 3, 3)), personas=[_persona("34100046", "P-46", "asegurado")],
         bienes=[{"tipo": "vehiculo", "identificador": "AD331PQ"}], estado=Siniestro.CERRADO,
         cierre=_cierre("aprobado", 6, "Daños consistentes con el evento climático informado.", _momento(2026, 8, 10, 12)))
    caso("pe08", "EXP-2026-0117", tipo="Robo de notebook", fecha_hecho=_momento(2026, 7, 10, 13, 0), fecha_denuncia=date(2026, 7, 11),
         poliza=_poliza("EQP-000044", date(2025, 5, 1), date(2025, 5, 3)), personas=[_persona("35200047", "P-47", "asegurado")],
         bienes=[{"tipo": "computadora", "identificador": "SN-8F09X2", "descripcion": "Notebook (ficticia)"}], estado=Siniestro.CERRADO,
         cierre=_cierre("aprobado", 8, "Denuncia y factura coinciden con el relato.", _momento(2026, 8, 5, 12)))
    caso("pe08", "EXP-2026-0158", tipo="Robo en comercio", fecha_hecho=_momento(2026, 8, 21, 22, 0), fecha_denuncia=date(2026, 8, 22),
         poliza=_poliza("COM-000090", date(2025, 6, 1), date(2025, 6, 3)), personas=[_persona("36300048", "P-48", "asegurado")],
         bienes=[{"tipo": "otro", "identificador": "Local 12", "descripcion": "Local comercial (ficticio)"}], estado=Siniestro.BORRADOR)

    # Cada caso confirmado se evalúa cuando ya está cargada toda la red, para que las evaluaciones vean todos los antecedentes
    for s in confirmados:
        if s.estado != Siniestro.ANULADO and s.estado != Siniestro.BORRADOR:
            guardar_evaluacion(s, "confirmacion", creada_en=s.confirmado_en)
    return u
