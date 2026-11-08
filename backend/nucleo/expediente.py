"""Servicios de dominio del expediente: numeración, personas, bienes, cierres y fechas."""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Bien, BienAfectado, Cierre, Participacion, Persona, Poliza, Siniestro
from .normalizacion import normalizar_identificador_bien, normalizar_identificador_persona


def fecha_local(momento):
    """Fecha (sin hora) en la zona horaria del proyecto. Es la `H` de las reglas."""
    if momento is None:
        return None
    if timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    return timezone.localtime(momento).date()


def generar_numero_expediente(ahora=None):
    """`EXP-AAAA-NNNN`: el siguiente número libre del año."""
    anio = (ahora or timezone.now()).year
    prefijo = f"EXP-{anio}-"
    mayor = 0
    for numero in Siniestro.objects.filter(numero_expediente__startswith=prefijo).values_list("numero_expediente", flat=True):
        encontrado = re.fullmatch(re.escape(prefijo) + r"(\d+)", numero)
        if encontrado:
            mayor = max(mayor, int(encontrado.group(1)))
    return f"{prefijo}{mayor + 1:04d}"


def guardar_poliza(datos, poliza=None):
    """Crea o actualiza la póliza del siniestro (una por siniestro)."""
    if not datos:
        return poliza
    campos = {c: datos.get(c) for c in ("numero", "compania", "cobertura", "inicio_vigencia", "primer_pago") if c in datos}
    campos["numero"] = campos.get("numero") or ""
    for texto in ("compania", "cobertura"):
        if campos.get(texto) is None:
            campos[texto] = ""
    if poliza is None:
        return Poliza.objects.create(**campos)
    for campo, valor in campos.items():
        setattr(poliza, campo, valor)
    poliza.save()
    return poliza


def reemplazar_personas(siniestro, personas):
    """Reemplaza las participaciones. La persona se reutiliza por (tipo, identificador) y no se pisa su nombre."""
    siniestro.participaciones.all().delete()
    for datos in personas:
        persona, _ = Persona.objects.get_or_create(
            tipo_identificador=datos.get("tipo_identificador") or Persona.DNI,
            identificador=normalizar_identificador_persona(datos["identificador"]),
            defaults={"nombre": datos.get("nombre") or normalizar_identificador_persona(datos["identificador"])},
        )
        for rol in dict.fromkeys(datos.get("roles") or []):
            Participacion.objects.get_or_create(siniestro=siniestro, persona=persona, rol=rol)


def reemplazar_bienes(siniestro, bienes):
    """Reemplaza los bienes afectados. El bien se reutiliza por `identificador_norm`."""
    siniestro.bienes_afectados.all().delete()
    for datos in bienes:
        bien = Bien.objects.filter(identificador_norm=normalizar_identificador_bien(datos["identificador"])).first()
        if bien is None:
            bien = Bien.objects.create(
                tipo=datos.get("tipo") or "otro",
                identificador=datos["identificador"],
                descripcion=datos.get("descripcion") or "",
                atributos=datos.get("atributos") or {},
            )
        BienAfectado.objects.get_or_create(
            siniestro=siniestro, bien=bien, defaults={"detalle_dano": datos.get("detalle_dano") or ""}
        )


def cierres_vigentes(ids_siniestro):
    """`{siniestro_id: Cierre}` con el cierre vigente (el último por fecha e id) de cada siniestro."""
    consulta = (
        Cierre.objects.filter(siniestro_id__in=list(ids_siniestro))
        .order_by("siniestro_id", "-creado_en", "-id")
        .distinct("siniestro_id")
    )
    return {c.siniestro_id: c for c in consulta}


def cierre_vigente(siniestro):
    return cierres_vigentes([siniestro.pk]).get(siniestro.pk)


def crear_siniestro_con_datos(*, perito, numero_expediente=None, poliza=None, personas=(), bienes=(), **campos):
    """Crea un siniestro con póliza, personas y bienes. Reintenta si el número generado se ocupó."""
    for intento in range(5):
        numero = numero_expediente or generar_numero_expediente()
        try:
            with transaction.atomic():
                siniestro = Siniestro.objects.create(
                    espacio=perito.espacio, perito=perito, numero_expediente=numero, poliza=guardar_poliza(poliza), **campos
                )
                reemplazar_personas(siniestro, personas)
                reemplazar_bienes(siniestro, bienes)
                return siniestro
        except IntegrityError:
            if numero_expediente or intento == 4:
                raise
