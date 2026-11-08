"""T07 / T09 · HU-08 (coincidencias y promedio), HU-11 (resumen minimizado), HU-15 (auditoría) y HU-17 (perfil)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from nucleo.fabrica import crear_cierre, crear_siniestro
from nucleo.models import Auditoria, Siniestro
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

P17 = {"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado", "conductor"]}
P52 = {"tipo_identificador": "DNI", "identificador": "20222052", "nombre": "P-52", "roles": ["asegurado"]}
POLIZA = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo",
          "inicio_vigencia": "2026-07-20", "primer_pago": "2026-08-04"}


@pytest.fixture
def red(norte, sur, perito08, perito11, perito15):
    """EXP-ORIGEN (Norte, PE-08, confirmado) y antecedentes en los dos espacios."""
    ahora = timezone.now()
    r = type("Red", (), {})()
    r.origen = crear_siniestro(perito08, "EXP-ORIGEN", tipo="Incendio total", fecha_hecho=ahora - timedelta(days=20), poliza=POLIZA,
                               relato="Relato privado del origen.", personas=[P17], bienes=["AB-123-CD"])
    r.cerrado = crear_siniestro(
        perito15, "S-CERRADO", tipo="Robo parcial de vehículo", fecha_hecho=ahora - timedelta(days=400), personas=[P52],
        bienes=[{"tipo": "vehiculo", "identificador": "AB123CD", "detalle_dano": "Daño privado del antecedente"}],
        relato="Relato privado del antecedente.", estado="cerrado",
        cierre={"resultado_reclamo": "aprobado", "irregularidad": False, "valoracion": 7,
                "conclusion": "Conclusión privada", "justificacion": "Faltó la denuncia policial original."},
    )
    r.por_persona = crear_siniestro(
        perito11, "S-PERSONA", tipo="Choque", fecha_hecho=ahora - timedelta(days=200), personas=[dict(P17, roles=["testigo"])],
        estado="cerrado", cierre={"resultado_reclamo": "rechazado", "irregularidad": True, "valoracion": 3, "justificacion": "Inconsistencias."},
    )
    r.en_analisis = crear_siniestro(perito11, "S-EN-ANALISIS", fecha_hecho=ahora - timedelta(days=100), bienes=["AB123CD"])
    r.anulado = crear_siniestro(perito11, "S-ANULADO", fecha_hecho=ahora - timedelta(days=50), bienes=["AB123CD"], estado="anulado")
    r.borrador = crear_siniestro(perito11, "S-BORRADOR", fecha_hecho=ahora - timedelta(days=60), bienes=["AB123CD"], estado="borrador")
    r.otro = crear_siniestro(perito15, "S-SIN-VINCULO", fecha_hecho=ahora - timedelta(days=60), bienes=["ZZ999ZZ"])
    return r


# --- HU-08 ---------------------------------------------------------------------------
def test_hu08_aparecen_los_antecedentes_validos_que_comparten_persona_o_bien(red, perito08):
    cuerpo = cliente_de(perito08).get(f"/api/siniestros/{red.origen.id}/coincidencias").json()
    assert {r["numero_expediente"] for r in cuerpo["resultados"]} == {"S-CERRADO", "S-PERSONA", "S-EN-ANALISIS"}
    assert cuerpo["total"] == 3 and cuerpo["pagina"] == 1 and cuerpo["paginas"] == 1 and cuerpo["mensaje_vacio"] is None
    por_numero = {r["numero_expediente"]: r for r in cuerpo["resultados"]}
    cerrado = por_numero["S-CERRADO"]
    assert cerrado["antecedente_id"] == red.cerrado.id and cerrado["tipo"] == "Robo parcial de vehículo"
    assert cerrado["estado"] == "cerrado" and cerrado["resultado_reclamo"] == "aprobado"
    assert cerrado["vinculos"] == [{"tipo": "bien", "etiqueta": "AB123CD", "rol_en_antecedente": "Bien afectado", "rol_en_caso": "Bien afectado"}]
    assert cerrado["descripcion_vinculo"] == "Mismo vehículo AB123CD"
    persona = por_numero["S-PERSONA"]["vinculos"][0]
    assert persona == {"tipo": "persona", "etiqueta": "P-17", "rol_en_antecedente": "testigo", "rol_en_caso": "asegurado y conductor"}
    assert por_numero["S-EN-ANALISIS"]["resultado_reclamo"] is None
    # no se filtra ningún identificador personal
    assert "30111017" not in str(cuerpo)


def test_hu08_el_antecedente_anulado_y_el_borrador_no_se_incluyen(red, perito08):
    numeros = {r["numero_expediente"] for r in cliente_de(perito08).get(f"/api/siniestros/{red.origen.id}/coincidencias").json()["resultados"]}
    assert "S-ANULADO" not in numeros and "S-BORRADOR" not in numeros and "S-SIN-VINCULO" not in numeros


def test_hu08_la_coincidencia_se_da_con_otros_espacios_y_no_une_nombres_parecidos(red, perito15):
    # misma persona con otro tipo de identificador no es la misma persona
    ajeno = crear_siniestro(perito15, "S-PASAPORTE", personas=[{"tipo_identificador": "PASAPORTE", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}])
    parecido = crear_siniestro(perito15, "S-NOMBRE", personas=[{"tipo_identificador": "DNI", "identificador": "55555555", "nombre": "P-17", "roles": ["asegurado"]}])
    numeros = {r["numero_expediente"] for r in cliente_de(red.origen.perito).get(f"/api/siniestros/{red.origen.id}/coincidencias").json()["resultados"]}
    assert "S-PASAPORTE" not in numeros and "S-NOMBRE" not in numeros
    assert ajeno.pk and parecido.pk


def test_hu08_un_caso_sin_coincidencias_informa_que_no_hay_antecedentes_accesibles(perito08):
    solo = crear_siniestro(perito08, "EXP-SOLO", personas=[], bienes=["QQ111QQ"])
    cuerpo = cliente_de(perito08).get(f"/api/siniestros/{solo.pk}/coincidencias").json()
    assert cuerpo["resultados"] == [] and cuerpo["total"] == 0
    assert cuerpo["mensaje_vacio"] == "No hay antecedentes accesibles en la red"
    assert cuerpo["promedio_valoracion"] == {"promedio": None, "cantidad": 0}


def test_hu08_el_promedio_de_valoracion_se_calcula_al_vuelo_y_no_se_guarda(red, perito08, perito15):
    cliente = cliente_de(perito08)
    cuerpo = cliente.get(f"/api/siniestros/{red.origen.id}/coincidencias").json()
    assert cuerpo["promedio_valoracion"] == {"promedio": 5.0, "cantidad": 2}  # 7 y 3; el que está en análisis no cuenta
    # si cambia la valoración vigente, el promedio se recalcula
    crear_cierre(red.cerrado, red.cerrado.perito, valoracion=9, motivo_cambio="Ajuste", creado_en=timezone.now() + timedelta(seconds=5))
    assert cliente.get(f"/api/siniestros/{red.origen.id}/coincidencias").json()["promedio_valoracion"] == {"promedio": 6.0, "cantidad": 2}
    # no queda guardado en ninguna tabla de personas: no hay campo de promedio en la persona ni en la evaluación
    from nucleo.models import Evaluacion, Persona

    assert not any("promedio" in f.name for f in Persona._meta.get_fields())
    assert not any("promedio" in f.name for f in Evaluacion._meta.get_fields())


def test_hu08_los_resultados_se_paginan_de_a_20(perito08):
    origen = crear_siniestro(perito08, "EXP-PAGINAS", personas=[], bienes=["PAG111"])
    for i in range(25):
        crear_siniestro(perito08, f"S-PAG-{i:02d}", fecha_hecho=timezone.now() - timedelta(days=i + 1), personas=[], bienes=["PAG111"])
    cliente = cliente_de(perito08)
    primera = cliente.get(f"/api/siniestros/{origen.pk}/coincidencias").json()
    segunda = cliente.get(f"/api/siniestros/{origen.pk}/coincidencias?pagina=2").json()
    assert (primera["total"], primera["paginas"], len(primera["resultados"])) == (25, 2, 20)
    assert (segunda["pagina"], len(segunda["resultados"])) == (2, 5)
    assert not {r["antecedente_id"] for r in primera["resultados"]} & {r["antecedente_id"] for r in segunda["resultados"]}
    assert cliente.get(f"/api/siniestros/{origen.pk}/coincidencias?pagina=abc").json()["pagina"] == 1


def test_hu08_cada_consulta_de_coincidencias_se_audita(red, perito08):
    cliente_de(perito08).get(f"/api/siniestros/{red.origen.id}/coincidencias")
    registro = Auditoria.objects.get(accion="ver_coincidencias")
    assert registro.usuario_id == perito08.id and registro.siniestro_origen_id == red.origen.id and registro.resultado == "permitido"


# --- HU-11 ---------------------------------------------------------------------------
def resumen(red, perito, antecedente):
    return cliente_de(perito).get(f"/api/siniestros/{red.origen.id}/antecedentes/{antecedente.id}/resumen")


def test_hu11_el_resumen_trae_tipo_fecha_vinculo_resultado_irregularidad_valoracion_justificacion_y_perito(red, perito08):
    respuesta = resumen(red, perito08, red.cerrado)
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["numero_expediente"] == "S-CERRADO" and cuerpo["tipo"] == "Robo parcial de vehículo"
    assert cuerpo["fecha_hecho"] == (timezone.localtime(red.cerrado.fecha_hecho).date()).isoformat()
    assert cuerpo["vinculos"] == [{"tipo": "bien", "etiqueta": "AB123CD", "rol_en_antecedente": "Bien afectado"}]
    assert cuerpo["cerrado"] is True and cuerpo["estado_texto"] == "Cerrado"
    assert cuerpo["resultado_reclamo"] == "aprobado" and cuerpo["irregularidad"] is False
    assert cuerpo["valoracion"] == 7 and cuerpo["valoracion_texto"] == "Verificado con observaciones menores"
    assert cuerpo["justificacion"] == "Faltó la denuncia policial original."
    assert cuerpo["perito_responsable"] == {"nombre": "PE-15"}
    assert cuerpo["origen"] == {"id": red.origen.id, "numero_expediente": "EXP-ORIGEN"}
    assert "quedan en el expediente de origen" in cuerpo["no_se_muestra"]


def test_hu11_el_resumen_no_muestra_documentos_fotos_notas_ni_datos_de_contacto(red, perito08):
    from nucleo.models import Nota

    Nota.objects.create(siniestro=red.cerrado, autor=red.cerrado.perito, texto="nota privada del antecedente")
    cuerpo = resumen(red, perito08, red.cerrado).json()
    texto = str(cuerpo)
    for prohibido in ("Relato privado", "Daño privado", "Conclusión privada", "nota privada", "20222052", "30111017", "P-52"):
        assert prohibido not in texto, prohibido
    for campo in ("documentos", "notas", "relato", "detalle_dano", "conclusion", "telefono", "dni", "lugar", "fotos"):
        assert campo not in cuerpo
    assert not any("@" in str(valor) for clave, valor in cuerpo.items() if clave != "contacto_perito")


def test_hu11_las_personas_se_identifican_por_el_nombre_del_caso_de_origen_y_nunca_por_su_identificador(red, perito08):
    cuerpo = resumen(red, perito08, red.por_persona).json()
    assert cuerpo["vinculos"] == [{"tipo": "persona", "etiqueta": "P-17", "rol_en_antecedente": "testigo"}]
    assert "30111017" not in str(cuerpo)
    assert cuerpo["irregularidad"] is True and cuerpo["resultado_reclamo"] == "rechazado"


def test_hu11_si_el_perito_habilito_su_contacto_se_muestra_el_correo(red, perito08):
    cuerpo = resumen(red, perito08, red.cerrado).json()  # PE-15 tiene el contacto visible
    assert cuerpo["contacto_perito"] == {"email": "pe15@correo.test"}


def test_hu11_si_no_lo_habilito_el_correo_no_se_muestra(red, perito08):
    cuerpo = resumen(red, perito08, red.por_persona).json()  # PE-11 no lo tiene visible
    assert cuerpo["contacto_perito"] is None
    assert "pe11@correo.test" not in str(cuerpo)


def test_hu11_un_caso_en_analisis_muestra_solo_en_analisis_sin_datos_de_cierre(red, perito08):
    cuerpo = resumen(red, perito08, red.en_analisis).json()
    assert cuerpo["estado_texto"] == "En análisis" and cuerpo["cerrado"] is False
    for campo in ("resultado_reclamo", "irregularidad", "valoracion", "valoracion_texto", "justificacion"):
        assert cuerpo[campo] is None


def test_hu11_pedir_un_resumen_sin_siniestro_confirmado_que_lo_vincule_se_rechaza(red, perito08):
    for antecedente in (red.otro, red.anulado, red.borrador):
        assert resumen(red, perito08, antecedente).status_code == 404
    assert Auditoria.objects.filter(accion="ver_resumen_antecedente", resultado="rechazado").count() == 3


def test_hu15_cada_consulta_de_resumen_guarda_usuario_origen_accion_fecha_y_resultado(red, perito08):
    resumen(red, perito08, red.cerrado)
    registro = Auditoria.objects.get(accion="ver_resumen_antecedente", resultado="permitido")
    assert registro.usuario_id == perito08.id
    assert registro.siniestro_origen_id == red.origen.id
    assert registro.objeto == f"siniestro:{red.cerrado.id}"
    assert registro.fecha is not None


def test_hu11_el_resumen_no_se_guarda(red, perito08):
    from nucleo.models import Documento, Nota

    antes = [m.objects.count() for m in (Siniestro, Documento, Nota)]
    resumen(red, perito08, red.cerrado)
    assert [m.objects.count() for m in (Siniestro, Documento, Nota)] == antes
