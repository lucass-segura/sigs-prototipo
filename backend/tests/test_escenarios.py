"""T08 / T14 · Los 30 escenarios con su resultado exacto, reproducibilidad y versionado (HU-09, HU-10, HU-12)."""
import io
from contextlib import redirect_stdout

import pytest
from django.core.management import call_command

from nucleo import escenarios
from nucleo.escenarios import ESCENARIOS, POR_ID
from nucleo.models import ConjuntoReglas, Evaluacion, Participacion, Senal, Siniestro, Usuario
from nucleo.motor import conjunto_a_dict, evaluar
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db


def _evaluacion_por_api(escenario_id):
    caso = Siniestro.objects.get(numero_expediente=escenarios.numero_expediente(escenario_id))
    perito = Usuario.objects.get(email=escenarios.EMAIL_PERITO)
    respuesta = cliente_de(perito).get(f"/api/siniestros/{caso.id}/evaluacion")
    assert respuesta.status_code == 200, respuesta.content
    return caso, perito, respuesta.json()


def test_hay_30_escenarios_con_36_activaciones_esperadas():
    assert len(ESCENARIOS) == 30
    assert sum(len(e.esperado["reglas"]) for e in ESCENARIOS[:24]) == 16
    assert sum(len(e.esperado["reglas"]) for e in ESCENARIOS[24:]) == 20
    assert sum(len(e.esperado["reglas"]) for e in ESCENARIOS) == 36


@pytest.mark.parametrize("escenario", ESCENARIOS, ids=[e.id for e in ESCENARIOS])
def test_escenario_da_las_reglas_los_puntos_el_total_y_la_prioridad_esperados(escenario):
    escenarios.crear_escenarios(solo=[escenario.id])
    _, _, evaluacion = _evaluacion_por_api(escenario.id)
    activadas = {s["codigo"]: s["puntos"] for s in evaluacion["senales"] if s["estado"] == "activada"}
    assert activadas == escenario.esperado["reglas"], escenario.descripcion
    assert evaluacion["puntaje"] == escenario.esperado["puntaje"]
    assert evaluacion["prioridad"] == escenario.esperado["prioridad"]
    no_evaluables = sorted(s["codigo"] for s in evaluacion["senales"] if s["estado"] == "no_evaluable")
    assert no_evaluables == sorted(escenario.esperado["no_evaluables"])
    # las 8 reglas siempre aparecen, con texto y con 0 puntos si no se activaron
    assert [s["codigo"] for s in evaluacion["senales"]] == [f"R0{i}" for i in range(1, 9)]
    for s in evaluacion["senales"]:
        assert s["texto"]
        if s["estado"] != "activada":
            assert s["puntos"] == 0
    assert evaluacion["version"] == "RS-1.0" and evaluacion["motivo"] == "escenario"


def test_hu09_c5_aplica_los_topes_por_grupo_y_el_total():
    escenarios.crear_escenarios(solo=["C5"])
    _, _, evaluacion = _evaluacion_por_api("C5")
    assert sum(s["puntos"] for s in evaluacion["senales"]) == 160
    assert {g: d["puntos"] for g, d in evaluacion["grupos"].items()} == {
        "Cobertura": 30, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10,
    }
    assert evaluacion["grupos"]["Cobertura"]["bruto"] == 45
    assert evaluacion["grupos"]["Persona"]["bruto"] == 50
    assert evaluacion["puntaje"] == 100


def test_c4_r03_se_activa_una_sola_vez_y_lista_los_tres_antecedentes():
    escenarios.crear_escenarios(solo=["C4"])
    _, _, evaluacion = _evaluacion_por_api("C4")
    r03 = next(s for s in evaluacion["senales"] if s["codigo"] == "R03")
    assert r03["puntos"] == 20
    assert [a["numero_expediente"] for a in r03["antecedentes"]] == ["ESC-C4-A1", "ESC-C4-A2", "ESC-C4-A3"]


def test_c3_un_mismo_antecedente_activa_reglas_de_grupos_distintos():
    escenarios.crear_escenarios(solo=["C3"])
    _, _, evaluacion = _evaluacion_por_api("C3")
    for codigo in ("R06", "R07"):
        senal = next(s for s in evaluacion["senales"] if s["codigo"] == codigo)
        assert [a["numero_expediente"] for a in senal["antecedentes"]] == ["ESC-C3-A1"]


def test_los_36_resultados_dan_0_falsos_positivos_y_0_falsos_negativos():
    escenarios.crear_escenarios()
    verdaderos_positivos = falsos_positivos = falsos_negativos = 0
    for escenario in ESCENARIOS:
        _, _, evaluacion = _evaluacion_por_api(escenario.id)
        obtenidas = {s["codigo"] for s in evaluacion["senales"] if s["estado"] == "activada"}
        esperadas = set(escenario.esperado["reglas"])
        verdaderos_positivos += len(obtenidas & esperadas)
        falsos_positivos += len(obtenidas - esperadas)
        falsos_negativos += len(esperadas - obtenidas)
    assert (verdaderos_positivos, falsos_positivos, falsos_negativos) == (36, 0, 0)


# --- Reproducibilidad ------------------------------------------------------------
@pytest.mark.parametrize("escenario_id", ["R04-A", "R06-C", "C2", "C5", "C6"])
def test_hu09_reevaluar_las_entradas_guardadas_con_la_misma_version_da_el_mismo_resultado(escenario_id):
    escenarios.crear_escenarios(solo=[escenario_id])
    _, _, evaluacion = _evaluacion_por_api(escenario_id)
    conjunto = ConjuntoReglas.objects.get(version=evaluacion["version"])
    de_nuevo = evaluar(evaluacion["entradas"], conjunto_a_dict(conjunto))
    assert de_nuevo["puntaje"] == evaluacion["puntaje"]
    assert de_nuevo["prioridad"] == evaluacion["prioridad"]
    assert de_nuevo["grupos"] == evaluacion["grupos"]
    assert de_nuevo["senales"] == evaluacion["senales"]


def test_hu09_recalcular_con_los_mismos_datos_crea_una_evaluacion_nueva_e_identica_sin_tocar_la_anterior():
    escenarios.crear_escenarios(solo=["C1"])
    caso, perito, primera = _evaluacion_por_api("C1")
    respuesta = cliente_de(perito).post(f"/api/siniestros/{caso.id}/recalcular")
    assert respuesta.status_code == 200
    segunda = respuesta.json()
    assert segunda["id"] != primera["id"] and segunda["motivo"] == "recalculo"
    for campo in ("puntaje", "prioridad", "grupos", "senales", "entradas", "version"):
        assert segunda[campo] == primera[campo], campo
    historial = cliente_de(perito).get(f"/api/siniestros/{caso.id}/evaluaciones").json()
    assert [h["id"] for h in historial] == [segunda["id"], primera["id"]]
    assert Evaluacion.objects.filter(siniestro=caso).count() == 2


# --- Versionado (HU-12) ------------------------------------------------------------
def _publicar(superadmin, version="RS-1.1", **cambios):
    cuerpo = {
        "version": version,
        "vigente_desde": "2026-12-01",
        "reglas": {"R08": {"parametros": {"plazo_dias": 10, "puntos": 7}, "puntos_max": 7}},
    }
    cuerpo.update(cambios)
    return cliente_de(superadmin).post("/api/reglas/versiones", cuerpo, format="json")


def test_hu12_una_version_nueva_no_altera_las_evaluaciones_viejas(superadmin):
    escenarios.crear_escenarios(solo=["R08-A"])
    caso, perito, antes = _evaluacion_por_api("R08-A")
    assert antes["puntaje"] == 10 and antes["version"] == "RS-1.0"
    senales_antes = list(Senal.objects.filter(evaluacion_id=antes["id"]).values_list("id", "regla_id", "estado", "puntos"))

    respuesta = _publicar(superadmin)
    assert respuesta.status_code == 201, respuesta.content
    assert respuesta.json()["version"] == "RS-1.1" and respuesta.json()["activo"] is True

    # la evaluación vieja conserva su versión, su puntaje y sus señales
    _, _, despues = _evaluacion_por_api("R08-A")
    assert despues["id"] == antes["id"] and despues["version"] == "RS-1.0" and despues["puntaje"] == 10
    assert list(Senal.objects.filter(evaluacion_id=antes["id"]).values_list("id", "regla_id", "estado", "puntos")) == senales_antes

    # recalcular usa la versión vigente: con plazo de 10 días la denuncia a 5 días ya no es tardía
    nueva = cliente_de(perito).post(f"/api/siniestros/{caso.id}/recalcular").json()
    assert nueva["version"] == "RS-1.1" and nueva["puntaje"] == 0
    # y la evaluación vieja sigue siendo reproducible con su versión original
    original = ConjuntoReglas.objects.get(version="RS-1.0")
    assert evaluar(antes["entradas"], conjunto_a_dict(original))["puntaje"] == 10


def test_hu12_reglas_muestra_la_version_vigente_y_la_anterior_queda_sin_edicion(superadmin, perito08):
    _publicar(superadmin)
    cuerpo = cliente_de(perito08).get("/api/reglas").json()
    assert cuerpo["vigente"]["version"] == "RS-1.1"
    assert [v["version"] for v in cuerpo["versiones"]] == ["RS-1.1", "RS-1.0"]
    r08 = next(r for r in cuerpo["vigente"]["reglas"] if r["codigo"] == "R08")
    assert r08["parametros"] == {"plazo_dias": 10, "puntos": 7} and r08["umbral_texto"] == "> 10 días: 7"
    # el resto se copió tal cual de la versión vigente
    r01 = next(r for r in cuerpo["vigente"]["reglas"] if r["codigo"] == "R01")
    assert r01["umbral_texto"] == "≤ 30 días: 25 · 31 a 60: 12"
    anterior_id = next(v["id"] for v in cuerpo["versiones"] if v["version"] == "RS-1.0")
    anterior = cliente_de(perito08).get(f"/api/reglas/versiones/{anterior_id}").json()
    assert anterior["activo"] is False
    assert next(r for r in anterior["reglas"] if r["codigo"] == "R08")["parametros"] == {"plazo_dias": 3, "puntos": 10}
    assert ConjuntoReglas.objects.filter(activo=True).count() == 1


def test_hu12_publicar_una_version_repetida_o_invalida_se_rechaza(superadmin):
    assert _publicar(superadmin, version="RS-1.0").status_code == 400
    assert _publicar(superadmin, version="").status_code == 400
    assert _publicar(superadmin, vigente_desde="mañana").status_code == 400
    assert _publicar(superadmin, reglas={"R99": {"parametros": {}}}).status_code == 400
    assert _publicar(superadmin, reglas={"R08": {"parametros": {"plazo_dias": 3}}}).status_code == 400
    assert ConjuntoReglas.objects.filter(activo=True).get().version == "RS-1.0"


def test_hu12_la_nueva_version_puede_cambiar_los_topes(superadmin):
    topes = {"grupos": {"Cobertura": 20, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10}, "total": 100,
             "prioridad": {"media": 25, "alta": 50}}
    assert _publicar(superadmin, version="RS-1.2", reglas={}, topes=topes).status_code == 201
    assert ConjuntoReglas.objects.get(version="RS-1.2").topes["grupos"]["Cobertura"] == 20
    assert ConjuntoReglas.objects.get(version="RS-1.0").topes["grupos"]["Cobertura"] == 30


# --- evaluar_escenarios ---------------------------------------------------------------
def test_evaluar_escenarios_imprime_las_metricas_y_sale_con_codigo_0():
    escenarios.crear_escenarios()
    salida = io.StringIO()
    with redirect_stdout(salida):
        call_command("evaluar_escenarios", stdout=salida)  # no lanza SystemExit: código de salida 0
    texto = salida.getvalue()
    assert "Precisión: 100 %" in texto and "Sensibilidad: 100 %" in texto
    assert "VP 36" in texto and "FP 0" in texto and "FN 0" in texto
    for escenario in ESCENARIOS:
        assert escenario.id in texto


def test_evaluar_escenarios_no_guarda_nada():
    escenarios.crear_escenarios()
    antes = (Evaluacion.objects.count(), Senal.objects.count())
    call_command("evaluar_escenarios", stdout=io.StringIO())
    assert (Evaluacion.objects.count(), Senal.objects.count()) == antes


def test_evaluar_escenarios_sale_con_codigo_1_si_algo_no_coincide():
    escenarios.crear_escenarios()
    for sufijo in ("A1", "A2"):  # los dos previos dejan de compartir la persona: R03-A no se activa
        Participacion.objects.filter(siniestro__numero_expediente=f"ESC-R03-A-{sufijo}").delete()
    salida = io.StringIO()
    with pytest.raises(SystemExit) as salio:
        call_command("evaluar_escenarios", stdout=salida)
    assert salio.value.code == 1
    assert "R03-A" in salida.getvalue() and "FN 1" in salida.getvalue()


def test_seed_escenarios_si_vacia_no_duplica():
    call_command("seed_escenarios", "--si-vacia", stdout=io.StringIO())
    cantidad = Siniestro.objects.count()
    assert cantidad > 30
    salida = io.StringIO()
    call_command("seed_escenarios", "--si-vacia", stdout=salida)
    assert Siniestro.objects.count() == cantidad
    assert "ya existen" in salida.getvalue().lower()
    assert POR_ID["C5"].esperado["puntaje"] == 100


# --- HU-09 criterio 2 y HU-10: explicación de cada regla, por la API ---------------------------------
def _confirmar_por_api(perito, **cambios):
    from tests.conftest import cuerpo_siniestro

    cliente = cliente_de(perito)
    cuerpo = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True, **cambios), format="json")
    assert cuerpo.status_code == 201, cuerpo.content
    return cliente, cuerpo.json()["id"]


def test_hu09_un_caso_al_que_le_falta_una_fecha_deja_esa_regla_no_evaluable_y_suma_cero(perito08):
    poliza = {"numero": "AUT-1", "compania": "X", "cobertura": "Y", "inicio_vigencia": "2026-07-20", "primer_pago": None}
    cliente, id_ = _confirmar_por_api(perito08, poliza=poliza)
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    r02 = next(s for s in evaluacion["senales"] if s["codigo"] == "R02")
    assert r02["estado"] == "no_evaluable" and r02["puntos"] == 0
    assert evaluacion["puntaje"] == 25  # solo R01: la regla no evaluable no suma


def test_hu10_cada_regla_se_muestra_con_sus_puntos_su_umbral_y_el_dato_del_caso(perito08):
    cliente, id_ = _confirmar_por_api(perito08)
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    r01 = next(s for s in evaluacion["senales"] if s["codigo"] == "R01")
    assert r01["nombre"] == "Cobertura reciente" and r01["grupo"] == "Cobertura" and r01["puntos"] == 25 and r01["puntos_max"] == 25
    assert r01["texto"] == "El hecho ocurrió 23 días después del inicio de vigencia. Umbral 30 días."
    assert r01["dato"]["dias"] == 23 and r01["dato"]["umbral_dias"] == 30
    r08 = next(s for s in evaluacion["senales"] if s["codigo"] == "R08")
    assert r08["estado"] == "no_activada" and r08["texto"] == "La denuncia se hizo 2 días después del hecho. Plazo 3 días."


def test_hu10_una_regla_no_evaluable_indica_que_dato_falto(perito08):
    for campo, regla, dato in (("fecha_denuncia", "R08", "de denuncia"),):
        cliente, id_ = _confirmar_por_api(perito08, **{campo: None})
        evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
        senal = next(s for s in evaluacion["senales"] if s["codigo"] == regla)
        assert senal["estado"] == "no_evaluable"
        assert senal["texto"] == f"No se pudo evaluar: falta la fecha {dato}."
    poliza = {"numero": "AUT-2", "compania": "X", "cobertura": "Y", "inicio_vigencia": None, "primer_pago": "2026-08-04"}
    cliente, id_ = _confirmar_por_api(perito08, poliza=poliza, numero_expediente="EXP-OTRO", bienes=[{"tipo": "otro", "identificador": "XYZ"}])
    r01 = next(s for s in cliente.get(f"/api/siniestros/{id_}/evaluacion").json()["senales"] if s["codigo"] == "R01")
    assert r01["texto"] == "No se pudo evaluar: falta la fecha de inicio de vigencia."
