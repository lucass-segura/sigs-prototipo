"""F2 · Nombre, descripción y atributos son del caso: no se filtran de un espacio a otro (§6 y §8).

No hay buscador de personas: crear un borrador solo con un DNI o una patente no puede devolver lo que
otro espacio escribió en su expediente.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from nucleo.fabrica import crear_siniestro
from nucleo.models import Bien, BienAfectado, Participacion, Persona
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

DNI = "27.555.111"
PATENTE = "XY-987 ZW"
NOMBRE_SUR = "Juana Real Secreta"
SECRETOS_SUR = [NOMBRE_SUR, "MOTOR-SECRETO-77", "CHASIS-SECRETO-88", "Descripción secreta del Sur", "Detalle secreto del Sur"]
PERSONA_SUR = {"tipo_identificador": "DNI", "identificador": DNI, "nombre": NOMBRE_SUR, "roles": ["asegurado"]}
BIEN_SUR = {
    "tipo": "vehiculo", "identificador": PATENTE, "descripcion": "Descripción secreta del Sur",
    "detalle_dano": "Detalle secreto del Sur", "atributos": {"motor": "MOTOR-SECRETO-77", "chasis": "CHASIS-SECRETO-88"},
}
POLIZA = cuerpo_siniestro()["poliza"]


@pytest.fixture
def caso_sur(perito15):
    """Antecedente del espacio Sur, cerrado, con el nombre y los atributos que escribió su perito."""
    return crear_siniestro(
        perito15, "EXP-SUR", fecha_hecho=timezone.now() - timedelta(days=90), personas=[PERSONA_SUR], bienes=[BIEN_SUR],
        estado="cerrado", cierre={"resultado_reclamo": "aprobado", "irregularidad": False, "valoracion": 8, "justificacion": "Sin observaciones."},
    )


def borrador_con_dni(cliente, nombre="", **cambios):
    """Borrador que solo trae el DNI y la patente (nombre y descripción vacíos)."""
    cuerpo = cuerpo_siniestro(
        personas=[{"tipo_identificador": "DNI", "identificador": DNI, "nombre": nombre, "roles": ["asegurado"]}],
    )
    cuerpo["bienes"] = [{"tipo": "vehiculo", "identificador": PATENTE}]
    cuerpo.update(cambios)
    return cliente.post("/api/siniestros", cuerpo, format="json")


def sin_secretos(cuerpo, secretos=SECRETOS_SUR):
    texto = str(cuerpo)
    return [s for s in secretos if s in texto]


def test_f2_un_borrador_con_solo_dni_y_patente_no_devuelve_lo_que_escribio_otro_espacio(caso_sur, perito08):
    respuesta = borrador_con_dni(cliente_de(perito08))
    assert respuesta.status_code == 201, respuesta.content
    cuerpo = respuesta.json()
    assert sin_secretos(cuerpo) == []
    assert cuerpo["personas"][0]["nombre"] == ""
    assert cuerpo["bienes"][0]["descripcion"] == "" and cuerpo["bienes"][0]["atributos"] == {}
    # lo mismo al abrir el expediente
    detalle = cliente_de(perito08).get(f"/api/siniestros/{cuerpo['id']}").json()
    assert sin_secretos(detalle) == []


def test_f2_al_editar_el_borrador_tampoco_se_filtra(caso_sur, perito08):
    cliente = cliente_de(perito08)
    id_ = borrador_con_dni(cliente).json()["id"]
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"tipo": "Otro", "bienes": [{"tipo": "vehiculo", "identificador": PATENTE}]}, format="json")
    assert respuesta.status_code == 200
    assert sin_secretos(respuesta.json()) == []


def test_f2_cada_caso_guarda_el_nombre_la_descripcion_y_los_atributos_que_escribio(perito08, perito11):
    bien = {"tipo": "vehiculo", "identificador": PATENTE, "descripcion": "Sedán del caso A", "atributos": {"motor": "A-1"}}
    primero = borrador_con_dni(cliente_de(perito08), nombre="Ana", bienes=[bien]).json()
    segundo = borrador_con_dni(
        cliente_de(perito11), nombre="Ana M.", bienes=[dict(bien, descripcion="Sedán del caso B", atributos={"motor": "B-2"})]
    ).json()
    assert [p["nombre"] for p in primero["personas"]] == ["Ana"] and [p["nombre"] for p in segundo["personas"]] == ["Ana M."]
    assert (primero["bienes"][0]["descripcion"], primero["bienes"][0]["atributos"]) == ("Sedán del caso A", {"motor": "A-1"})
    assert (segundo["bienes"][0]["descripcion"], segundo["bienes"][0]["atributos"]) == ("Sedán del caso B", {"motor": "B-2"})
    assert Persona.objects.count() == 1 and Bien.objects.count() == 1
    assert Participacion.objects.filter(siniestro_id=primero["id"]).get().nombre == "Ana"
    assert BienAfectado.objects.filter(siniestro_id=segundo["id"]).get().atributos == {"motor": "B-2"}


def test_f2_coincidencias_evaluacion_y_resumen_no_muestran_el_nombre_de_otro_espacio(caso_sur, perito08):
    cliente = cliente_de(perito08)
    id_ = borrador_con_dni(cliente, nombre="Nombre Norte", poliza=POLIZA).json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/confirmar").status_code == 200
    coincidencias = cliente.get(f"/api/siniestros/{id_}/coincidencias").json()
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    resumen = cliente.get(f"/api/siniestros/{id_}/antecedentes/{caso_sur.id}/resumen").json()
    for cuerpo in (coincidencias, evaluacion, resumen):
        assert sin_secretos(cuerpo) == []
    etiquetas = {v["etiqueta"] for v in resumen["vinculos"] if v["tipo"] == "persona"}
    assert etiquetas == {"Nombre Norte"}
    assert [v["etiqueta"] for v in coincidencias["resultados"][0]["vinculos"] if v["tipo"] == "persona"] == ["Nombre Norte"]
    assert any("Nombre Norte" in s["texto"] for s in evaluacion["senales"] if s["codigo"] == "R03")


def test_f2_si_el_perito_no_escribio_nombre_las_etiquetas_no_usan_el_del_otro_espacio_ni_el_dni(caso_sur, perito08):
    cliente = cliente_de(perito08)
    id_ = borrador_con_dni(cliente, poliza=POLIZA).json()["id"]
    cliente.post(f"/api/siniestros/{id_}/confirmar")
    resumen = cliente.get(f"/api/siniestros/{id_}/antecedentes/{caso_sur.id}/resumen").json()
    coincidencias = cliente.get(f"/api/siniestros/{id_}/coincidencias").json()
    evaluacion = cliente.get(f"/api/siniestros/{id_}/evaluacion").json()
    # las entradas de la evaluación llevan el identificador (es el del propio caso); el resumen y las coincidencias no
    for cuerpo in (resumen, coincidencias):
        assert "27555111" not in str(cuerpo) and DNI not in str(cuerpo)
    assert sin_secretos(evaluacion) == []
    assert [v["etiqueta"] for v in resumen["vinculos"] if v["tipo"] == "persona"] == ["Persona sin nombre"]


def test_f2_el_espacio_sur_tampoco_ve_el_nombre_que_escribio_el_norte(perito08, perito15):
    nombre_norte = "Nombre Escrito En El Norte"
    norte = crear_siniestro(
        perito08, "EXP-NORTE", fecha_hecho=timezone.now() - timedelta(days=60), poliza=POLIZA, estado="cerrado",
        personas=[{"tipo_identificador": "DNI", "identificador": DNI, "nombre": nombre_norte, "roles": ["asegurado"]}],
        bienes=[{"tipo": "vehiculo", "identificador": PATENTE, "descripcion": "Descripción del Norte", "atributos": {"motor": "MOTOR-NORTE"}}],
        cierre={"resultado_reclamo": "aprobado", "irregularidad": False, "valoracion": 9, "justificacion": "Sin observaciones."},
    )
    cliente = cliente_de(perito15)
    id_ = borrador_con_dni(cliente, nombre="Juana (Sur)", poliza=POLIZA).json()["id"]
    cliente.post(f"/api/siniestros/{id_}/confirmar")
    cuerpos = [
        cliente.get(f"/api/siniestros/{id_}").json(),
        cliente.get(f"/api/siniestros/{id_}/coincidencias").json(),
        cliente.get(f"/api/siniestros/{id_}/evaluacion").json(),
        cliente.get(f"/api/siniestros/{id_}/antecedentes/{norte.id}/resumen").json(),
    ]
    for cuerpo in cuerpos:
        assert sin_secretos(cuerpo, [nombre_norte, "Descripción del Norte", "MOTOR-NORTE"]) == []
    assert [v["etiqueta"] for v in cuerpos[3]["vinculos"] if v["tipo"] == "persona"] == ["Juana (Sur)"]
