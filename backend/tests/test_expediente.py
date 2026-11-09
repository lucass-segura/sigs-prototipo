"""T05 / T06 · HU-03, HU-04, HU-05, HU-06, HU-07 y HU-16: registro, confirmación, documentos, notas, tareas y panel."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, Bien, Evaluacion, Persona, Siniestro, Tarea
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db


def crear(cliente, **cambios):
    return cliente.post("/api/siniestros", cuerpo_siniestro(**cambios), format="json")


# --- HU-03 Registro ---------------------------------------------------------------
def test_hu03_sin_fecha_del_hecho_el_sistema_indica_que_es_obligatoria(perito08):
    cuerpo = cuerpo_siniestro()
    del cuerpo["fecha_hecho"]
    respuesta = cliente_de(perito08).post("/api/siniestros", cuerpo, format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"fecha_hecho": ["La fecha del hecho es obligatoria."]}
    assert Siniestro.objects.count() == 0


def test_hu03_la_fecha_del_hecho_nula_tambien_se_rechaza(perito08):
    respuesta = crear(cliente_de(perito08), fecha_hecho=None)
    assert respuesta.status_code == 400 and respuesta.json() == {"fecha_hecho": ["La fecha del hecho es obligatoria."]}


def test_hu03_los_identificadores_se_normalizan_al_guardar(perito08):
    respuesta = crear(cliente_de(perito08))
    assert respuesta.status_code == 201, respuesta.content
    cuerpo = respuesta.json()
    assert cuerpo["bienes"][0]["identificador_norm"] == "AB123CD"
    assert cuerpo["personas"][0]["identificador"] == "30111017"
    assert Bien.objects.get().identificador_norm == "AB123CD"


def test_hu03_un_siniestro_guardado_sin_confirmar_queda_borrador_y_no_se_analiza(perito08):
    cliente = cliente_de(perito08)
    cuerpo = crear(cliente).json()
    assert cuerpo["estado"] == "borrador" and cuerpo["confirmado_en"] is None
    assert cuerpo["numero_expediente"].startswith("EXP-")
    assert Evaluacion.objects.count() == 0
    assert cliente.get(f"/api/siniestros/{cuerpo['id']}/evaluacion").status_code == 403
    assert cliente.get(f"/api/siniestros/{cuerpo['id']}/coincidencias").status_code == 403


def test_hu03_el_numero_de_expediente_se_genera_correlativo_o_se_respeta_el_indicado(perito08):
    cliente = cliente_de(perito08)
    anio = timezone.now().year
    assert crear(cliente).json()["numero_expediente"] == f"EXP-{anio}-0001"
    assert crear(cliente, personas=[], bienes=[{"tipo": "otro", "identificador": "XX1"}]).json()["numero_expediente"] == f"EXP-{anio}-0002"
    propio = crear(cliente, numero_expediente="EXP-2026-0147", bienes=[{"tipo": "otro", "identificador": "XX2"}])
    assert propio.status_code == 201 and propio.json()["numero_expediente"] == "EXP-2026-0147"
    repetido = crear(cliente, numero_expediente="EXP-2026-0147")
    assert repetido.status_code == 400 and "numero_expediente" in repetido.json()


def test_hu03_se_puede_editar_un_borrador_y_reemplaza_personas_y_bienes(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.patch(
        f"/api/siniestros/{id_}",
        {"tipo": "Robo parcial", "bienes": [{"tipo": "motocicleta", "identificador": "a-111 bb"}], "personas": []},
        format="json",
    )
    assert respuesta.status_code == 200, respuesta.content
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "Robo parcial"
    assert [b["identificador_norm"] for b in cuerpo["bienes"]] == ["A111BB"]
    assert cuerpo["personas"] == []


def test_hu03_no_se_edita_un_siniestro_confirmado(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente, confirmar=True).json()["id"]
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"tipo": "Otro"}, format="json")
    assert respuesta.status_code == 400
    assert Siniestro.objects.get(pk=id_).tipo == "Incendio total"


def test_hu03_la_persona_existente_se_reutiliza_y_no_se_pisa_su_nombre(perito08, perito15):
    crear(cliente_de(perito15), numero_expediente="S-1")
    crear(cliente_de(perito08), personas=[{"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "OTRO NOMBRE", "roles": ["testigo"]}])
    persona = Persona.objects.get(identificador="30111017")
    assert persona.nombre == "P-17" and Persona.objects.count() == 1


def test_hu03_un_rol_invalido_o_una_persona_sin_rol_se_rechazan(perito08):
    cliente = cliente_de(perito08)
    assert crear(cliente, personas=[{"identificador": "1", "nombre": "X", "roles": ["jefe"]}]).status_code == 400
    assert crear(cliente, personas=[{"identificador": "1", "nombre": "X", "roles": []}]).status_code == 400
    assert Siniestro.objects.count() == 0


# --- HU-04 Confirmación -----------------------------------------------------------
def test_hu04_un_borrador_completo_pasa_a_en_analisis_y_se_evalua(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/confirmar")
    assert respuesta.status_code == 200, respuesta.content
    assert respuesta.json()["estado"] == "en_analisis" and respuesta.json()["confirmado_en"]
    # dispara la búsqueda de coincidencias y el cálculo del indicador
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    assert evaluacion["motivo"] == "confirmacion" and evaluacion["version"] == "RS-1.0"
    assert cliente.get(f"/api/siniestros/{id_}/coincidencias").status_code == 200
    assert Auditoria.objects.filter(usuario=perito08, accion="confirmar_siniestro", resultado="permitido").exists()


def test_hu04_confirmar_calcula_el_indicador_con_las_reglas_vigentes(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente, confirmar=True).json()["id"]
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    activadas = {s["codigo"]: s["puntos"] for s in evaluacion["senales"] if s["estado"] == "activada"}
    assert activadas == {"R01": 25, "R02": 20}  # vigencia a 23 días y pago 8 días antes; la denuncia a 2 días no es tardía
    assert evaluacion["puntaje"] == 30 and evaluacion["prioridad"] == "media"  # Cobertura 45, con el tope 30


@pytest.mark.parametrize("quitar", ["poliza", "personas_y_bienes"])
def test_hu04_sin_poliza_o_sin_personas_ni_bienes_no_se_confirma(perito08, quitar):
    cliente = cliente_de(perito08)
    cambios = {"poliza": None} if quitar == "poliza" else {"personas": [], "bienes": []}
    id_ = crear(cliente, **cambios).json()["id"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/confirmar")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"detalle": "Para confirmar hacen falta la póliza, la fecha del hecho y al menos una persona o un bien."}
    assert Siniestro.objects.get(pk=id_).estado == "borrador"


def test_hu04_crear_con_confirmar_aplica_las_mismas_validaciones_y_no_deja_basura(perito08):
    respuesta = crear(cliente_de(perito08), poliza=None, confirmar=True)
    assert respuesta.status_code == 400
    assert Siniestro.objects.count() == 0


def test_hu04_no_se_confirma_dos_veces(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente, confirmar=True).json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/confirmar").status_code == 400
    assert Evaluacion.objects.filter(siniestro_id=id_).count() == 1


def test_hu04_confirmar_un_siniestro_recalcula_los_casos_en_analisis_que_comparten_persona_o_bien(perito08, perito15):
    # el caso del Norte ya está en análisis; en el Sur se confirma otro con el mismo vehículo
    c08 = cliente_de(perito08)
    id_norte = crear(c08, confirmar=True, fecha_hecho="2026-08-12T23:40:00").json()["id"]
    assert Evaluacion.objects.filter(siniestro_id=id_norte).count() == 1
    antes = c08.get(f"/api/siniestros/{id_norte}/evaluacion").json()
    c15 = cliente_de(perito15)
    previo = crear(
        c15, numero_expediente="S-2025-0381", fecha_hecho="2025-07-10T10:00:00",
        poliza=dict(cuerpo_siniestro()["poliza"], inicio_vigencia="2024-03-01", primer_pago="2024-03-05"),
        personas=[{"tipo_identificador": "DNI", "identificador": "99999999", "nombre": "P-52", "roles": ["asegurado"]}],
        confirmar=True,
    )
    assert previo.status_code == 201
    despues = c08.get(f"/api/siniestros/{id_norte}/evaluacion").json()
    assert despues["id"] != antes["id"] and despues["motivo"] == "antecedente_confirmado"
    assert despues["puntaje"] == antes["puntaje"] + 25 and Evaluacion.objects.filter(siniestro_id=id_norte).count() == 2
    assert next(s for s in despues["senales"] if s["codigo"] == "R06")["estado"] == "activada"


def test_hu04_un_borrador_ajeno_no_dispara_recalculos(perito08, perito15):
    c08 = cliente_de(perito08)
    id_norte = crear(c08, confirmar=True).json()["id"]
    crear(cliente_de(perito15), numero_expediente="S-BORRADOR")  # borrador con el mismo vehículo
    assert Evaluacion.objects.filter(siniestro_id=id_norte).count() == 1


# --- HU-05 Documentos --------------------------------------------------------------
def _subir(cliente, siniestro_id, nombre="foto.jpg", contenido=b"binario-ficticio", tipo="Fotografía"):
    return cliente.post(
        f"/api/siniestros/{siniestro_id}/documentos",
        {"archivo": SimpleUploadedFile(nombre, contenido, content_type="image/jpeg"), "tipo": tipo},
        format="multipart",
    )


def test_hu05_el_documento_cargado_aparece_en_la_lista_con_su_tipo_y_fecha_de_carga(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    subida = _subir(cliente, id_)
    assert subida.status_code == 201, subida.content
    lista = cliente.get(f"/api/siniestros/{id_}/documentos").json()
    assert len(lista) == 1
    assert lista[0]["tipo"] == "Fotografía" and lista[0]["nombre_original"] == "foto.jpg"
    assert lista[0]["estado"] == "recibido" and lista[0]["recibido_en"] and lista[0]["tamanio"] == len(b"binario-ficticio")
    assert Auditoria.objects.filter(usuario=perito08, accion="subir_documento").exists()


def test_hu05_la_descarga_la_hace_el_perito_responsable_por_el_endpoint_con_permiso(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    documento = _subir(cliente, id_, contenido=b"contenido-privado").json()
    respuesta = cliente.get(f"/api/documentos/{documento['id']}/descargar")
    assert respuesta.status_code == 200
    assert b"".join(respuesta.streaming_content) == b"contenido-privado"
    assert "attachment" in respuesta["Content-Disposition"] and "foto.jpg" in respuesta["Content-Disposition"]
    assert Auditoria.objects.filter(usuario=perito08, accion="descargar_documento", resultado="permitido").exists()


def test_hu05_el_archivo_no_tiene_url_publica_y_el_nombre_en_disco_es_opaco(perito08, settings):
    from pathlib import Path

    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    _subir(cliente, id_, nombre="../../etc/passwd")
    archivos = [p for p in Path(settings.DOCUMENTOS_DIR).rglob("*") if p.is_file()]
    assert len(archivos) == 1 and archivos[0].parent.name == str(id_)
    assert "passwd" not in archivos[0].name
    assert cliente.get(f"/documentos/{id_}/{archivos[0].name}").status_code == 404
    assert cliente.get(f"/api/documentos/{id_}/{archivos[0].name}").status_code == 404


def test_hu05_sin_archivo_o_sin_tipo_se_rechaza(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/documentos", {"tipo": "Foto"}, format="multipart").status_code == 400
    sin_tipo = cliente.post(
        f"/api/siniestros/{id_}/documentos", {"archivo": SimpleUploadedFile("a.txt", b"x")}, format="multipart"
    )
    assert sin_tipo.status_code == 400 and "tipo" in sin_tipo.json()


def test_hu05_el_documento_privado_no_se_ve_en_el_resumen_de_otro_perito(perito08, perito15):
    c08 = cliente_de(perito08)
    id_norte = crear(c08, confirmar=True).json()["id"]
    _subir(c08, id_norte, nombre="secreto.pdf", contenido=b"contenido-privado")
    c15 = cliente_de(perito15)
    id_sur = crear(c15, numero_expediente="S-SUR", confirmar=True, personas=[], fecha_hecho="2026-09-01T10:00:00").json()["id"]
    resumen = c15.get(f"/api/siniestros/{id_sur}/antecedentes/{id_norte}/resumen")
    assert resumen.status_code == 200
    texto = resumen.content.decode()
    assert "secreto.pdf" not in texto and "documento" not in resumen.json() and "documentos" not in resumen.json()
    # ... y tampoco se puede descargar
    documento_id = c08.get(f"/api/siniestros/{id_norte}/documentos").json()[0]["id"]
    assert c15.get(f"/api/documentos/{documento_id}/descargar").status_code == 404


# --- HU-06 Notas -------------------------------------------------------------------
def test_hu06_la_nota_queda_con_fecha_hora_y_autor(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/notas", {"texto": "Recibo el caso. Falta foto del chasis."}, format="json")
    assert respuesta.status_code == 201
    nota = respuesta.json()
    assert nota["texto"].startswith("Recibo el caso") and nota["autor"] == {"id": perito08.id, "nombre": "PE-08"}
    assert "T" in nota["creada_en"]  # fecha y hora
    assert cliente.get(f"/api/siniestros/{id_}/notas").json() == [nota]


def test_hu06_una_nota_vacia_se_rechaza(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/notas", {"texto": "  "}, format="json").status_code == 400


def test_hu06_la_nota_no_se_muestra_en_el_resumen_de_otro_perito(perito08, perito15):
    c08 = cliente_de(perito08)
    id_norte = crear(c08, confirmar=True).json()["id"]
    c08.post(f"/api/siniestros/{id_norte}/notas", {"texto": "nota privada del perito"}, format="json")
    c15 = cliente_de(perito15)
    id_sur = crear(c15, numero_expediente="S-SUR", confirmar=True, personas=[], fecha_hecho="2026-09-01T10:00:00").json()["id"]
    resumen = c15.get(f"/api/siniestros/{id_sur}/antecedentes/{id_norte}/resumen")
    assert resumen.status_code == 200 and "nota privada" not in resumen.content.decode()


# --- HU-07 Tareas ------------------------------------------------------------------
def test_hu07_la_tarea_nueva_con_vencimiento_aparece_pendiente(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Redactar informe", "vence_en": "2026-09-01"}, format="json")
    assert respuesta.status_code == 201
    tarea = respuesta.json()
    assert tarea["estado"] == "pendiente" and tarea["vence_en"] == "2026-09-01" and tarea["cambios"] == []
    assert cliente.get(f"/api/siniestros/{id_}/tareas").json()[0]["titulo"] == "Redactar informe"


def test_hu07_mover_una_tarea_cambia_su_estado_y_registra_el_cambio(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    tarea_id = cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Entrevista"}, format="json").json()["id"]
    respuesta = cliente.patch(f"/api/tareas/{tarea_id}", {"estado": "en_curso"}, format="json")
    assert respuesta.status_code == 200
    cliente.patch(f"/api/tareas/{tarea_id}", {"estado": "hecha"}, format="json")
    tarea = cliente.get(f"/api/siniestros/{id_}/tareas").json()[0]
    assert tarea["estado"] == "hecha"
    assert [(c["estado_anterior"], c["estado_nuevo"]) for c in tarea["cambios"]] == [("pendiente", "en_curso"), ("en_curso", "hecha")]
    assert tarea["cambios"][0]["usuario"]["nombre"] == "PE-08" and tarea["cambios"][0]["fecha"]
    assert Auditoria.objects.filter(usuario=perito08, accion="cambiar_estado_tarea").count() == 2


def test_hu07_un_estado_invalido_se_rechaza_y_no_cambia_nada(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    tarea_id = cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "X"}, format="json").json()["id"]
    assert cliente.patch(f"/api/tareas/{tarea_id}", {"estado": "inexistente"}, format="json").status_code == 400
    assert Tarea.objects.get(pk=tarea_id).estado == "pendiente"


def test_hu07_solo_el_perito_asignado_mueve_la_tarea_y_otro_perito_no_la_ve(perito08, perito11, perito15):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    tarea_id = cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "X"}, format="json").json()["id"]
    assert cliente_de(perito11).patch(f"/api/tareas/{tarea_id}", {"estado": "hecha"}, format="json").status_code == 404
    assert cliente_de(perito15).patch(f"/api/tareas/{tarea_id}", {"estado": "hecha"}, format="json").status_code == 404
    assert Tarea.objects.get(pk=tarea_id).estado == "pendiente"


def test_hu07_la_lista_general_de_tareas_trae_las_no_hechas_de_los_expedientes_propios(perito08, perito11):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Pendiente"}, format="json")
    hecha = cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Hecha"}, format="json").json()["id"]
    cliente.patch(f"/api/tareas/{hecha}", {"estado": "hecha"}, format="json")
    lista = cliente.get("/api/tareas").json()
    assert [t["titulo"] for t in lista] == ["Pendiente"]
    assert lista[0]["siniestro"]["id"] == id_ and lista[0]["siniestro"]["numero_expediente"].startswith("EXP-")
    assert cliente_de(perito11).get("/api/tareas").json() == []


# --- HU-16 Panel -------------------------------------------------------------------
def test_hu16_el_panel_ordena_por_prioridad_y_luego_por_fecha(perito08, perito11):
    ahora = timezone.now()
    base = {"poliza": {"numero": "P", "inicio_vigencia": "2025-01-01", "primer_pago": "2025-01-01"}}
    sin_evaluar = crear_siniestro(perito08, "EXP-BORR", estado="borrador", fecha_hecho=ahora - timedelta(days=1), **base)
    cliente = cliente_de(perito08)
    # tres confirmados con prioridades distintas
    alta = crear_siniestro(perito08, "EXP-ALTA", fecha_hecho=ahora - timedelta(days=30), **base)
    media_reciente = crear_siniestro(perito08, "EXP-MEDIA-1", fecha_hecho=ahora - timedelta(days=5), **base)
    media_vieja = crear_siniestro(perito08, "EXP-MEDIA-2", fecha_hecho=ahora - timedelta(days=60), **base)
    baja = crear_siniestro(perito08, "EXP-BAJA", fecha_hecho=ahora - timedelta(days=2), **base)
    ajeno = crear_siniestro(perito11, "EXP-AJENO", fecha_hecho=ahora - timedelta(days=1), **base)
    from nucleo.models import ConjuntoReglas

    conjunto = ConjuntoReglas.objects.get(version="RS-1.0")
    for siniestro, puntaje, prioridad in ((alta, 60, "alta"), (media_reciente, 30, "media"), (media_vieja, 30, "media"), (baja, 5, "baja"), (ajeno, 90, "alta")):
        Evaluacion.objects.create(siniestro=siniestro, conjunto=conjunto, puntaje=puntaje, prioridad=prioridad, entradas={}, motivo="recalculo")
    cuerpo = cliente.get("/api/siniestros").json()
    assert [i["numero_expediente"] for i in cuerpo["resultados"]] == ["EXP-ALTA", "EXP-MEDIA-1", "EXP-MEDIA-2", "EXP-BAJA", "EXP-BORR"]
    primero = cuerpo["resultados"][0]
    assert primero["prioridad"] == "alta" and primero["puntaje"] == 60 and primero["estado"] == "en_analisis"
    assert cuerpo["resultados"][-1]["prioridad"] is None and cuerpo["resultados"][-1]["puntaje"] is None
    assert set(primero) == {"id", "numero_expediente", "tipo", "fecha_hecho", "estado", "bien_principal", "prioridad", "puntaje", "tareas_pendientes"}
    assert sin_evaluar.pk  # el borrador aparece sin evaluar


def test_hu16_el_expediente_de_otro_perito_no_aparece_en_mi_panel(perito08, perito11):
    crear_siniestro(perito11, "EXP-DE-PE-11", fecha_hecho=timezone.now())
    propio = crear_siniestro(perito08, "EXP-DE-PE-08", fecha_hecho=timezone.now())
    cuerpo = cliente_de(perito08).get("/api/siniestros").json()
    assert [i["id"] for i in cuerpo["resultados"]] == [propio.pk]


def test_hu16_el_panel_cuenta_el_resumen_y_las_tareas_pendientes(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente, confirmar=True).json()["id"]
    hoy = timezone.localdate()
    cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Vence pronto", "vence_en": (hoy + timedelta(days=3)).isoformat()}, format="json")
    cliente.post(f"/api/siniestros/{id_}/tareas", {"titulo": "Vence lejos", "vence_en": (hoy + timedelta(days=30)).isoformat()}, format="json")
    cuerpo = cliente.get("/api/siniestros").json()
    assert cuerpo["resultados"][0]["tareas_pendientes"] == 2
    assert cuerpo["resultados"][0]["bien_principal"] == "AB123CD"
    assert cuerpo["resumen"] == {"en_analisis": 1, "prioridad_alta": 0, "tareas_vencen_semana": 1, "cerrados_mes": 0}
