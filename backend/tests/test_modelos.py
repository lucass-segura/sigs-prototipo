"""T02 · Modelo de datos: normalización, restricciones, triggers de la base y RS-1.0."""
import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from nucleo.models import (
    Auditoria,
    Bien,
    Cierre,
    ConjuntoReglas,
    EspacioTrabajo,
    Evaluacion,
    Persona,
    Regla,
    RegistroInmutable,
    Senal,
    Siniestro,
    Usuario,
)

pytestmark = pytest.mark.django_db


def _espacio(nombre="Espacio de prueba"):
    return EspacioTrabajo.objects.create(nombre=nombre)


def _perito(espacio, email="perito@sigs.test"):
    return Usuario.objects.create_user(email=email, nombre="Perito", rol="perito", espacio=espacio, password="Clave.Segura#1")


def _siniestro(espacio, perito, numero="EXP-T-0001"):
    return Siniestro.objects.create(
        espacio=espacio, perito=perito, numero_expediente=numero, tipo="Choque",
        fecha_hecho=timezone.now(), estado="en_analisis", confirmado_en=timezone.now(),
    )


def test_el_email_del_usuario_se_guarda_en_minusculas():
    espacio = _espacio()
    usuario = _perito(espacio, email="Perito.Mayusculas@SIGS.test")
    usuario.refresh_from_db()
    assert usuario.email == "perito.mayusculas@sigs.test"


def test_solo_el_superadministrador_puede_no_tener_espacio():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Usuario.objects.create_user(email="a@sigs.test", nombre="A", rol="perito", espacio=None, password="Clave.Segura#1")
    espacio = _espacio()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Usuario.objects.create_user(email="b@sigs.test", nombre="B", rol="superadministrador", espacio=espacio, password="Clave.Segura#1")
    superadmin = Usuario.objects.create_user(email="c@sigs.test", nombre="C", rol="superadministrador", espacio=None, password="Clave.Segura#1")
    assert superadmin.espacio_id is None


def test_is_active_depende_del_campo_activo():
    espacio = _espacio()
    usuario = _perito(espacio)
    assert usuario.is_active is True
    usuario.activo = False
    assert usuario.is_active is False


def test_persona_normaliza_el_identificador_y_es_unica_por_tipo():
    persona = Persona.objects.create(tipo_identificador="DNI", identificador="30.111 017", nombre="P-1")
    assert persona.identificador == "30111017"
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Persona.objects.create(tipo_identificador="DNI", identificador="30111017", nombre="Otro")
    # el mismo identificador con otro tipo es otra persona
    Persona.objects.create(tipo_identificador="PASAPORTE", identificador="30111017", nombre="P-2")


def test_bien_normaliza_el_identificador_y_es_unico():
    bien = Bien.objects.create(tipo="vehiculo", identificador="ab-123 cd")
    assert bien.identificador_norm == "AB123CD"
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Bien.objects.create(tipo="vehiculo", identificador="AB.123.CD")


def test_auditoria_no_se_puede_modificar_ni_borrar_desde_el_modelo():
    registro = Auditoria.objects.create(accion="prueba", objeto="x", resultado="permitido")
    registro.accion = "otra"
    with pytest.raises(RegistroInmutable):
        registro.save()
    with pytest.raises(RegistroInmutable):
        registro.delete()
    with pytest.raises(RegistroInmutable):
        Auditoria.objects.filter(pk=registro.pk).update(accion="otra")
    with pytest.raises(RegistroInmutable):
        Auditoria.objects.filter(pk=registro.pk).delete()


def test_auditoria_no_se_puede_modificar_con_sql_directo_como_usuario_de_la_aplicacion():
    registro = Auditoria.objects.create(accion="prueba", objeto="x", resultado="permitido")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)")
        _, es_superusuario = cursor.fetchone()
    assert es_superusuario is False
    for sentencia in (
        "UPDATE auditoria SET accion = 'manipulada' WHERE id = %s",
        "DELETE FROM auditoria WHERE id = %s",
    ):
        with pytest.raises(Exception) as error:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sentencia, [registro.pk])
        assert "no se pueden modificar ni borrar" in str(error.value)
    registro.refresh_from_db()
    assert registro.accion == "prueba"


@pytest.mark.parametrize("tabla", ["cierre", "evaluacion", "senal"])
def test_las_tablas_de_historial_bloquean_update_y_delete_en_la_base(tabla):
    espacio = _espacio()
    perito = _perito(espacio)
    siniestro = _siniestro(espacio, perito)
    cierre = Cierre.objects.create(
        siniestro=siniestro, perito=perito, resultado_reclamo="aprobado", irregularidad=False,
        conclusion="ok", valoracion=7, justificacion="Justificada",
    )
    conjunto = ConjuntoReglas.objects.get(version="RS-1.0")
    evaluacion = Evaluacion.objects.create(siniestro=siniestro, conjunto=conjunto, puntaje=0, prioridad="baja", entradas={}, motivo="confirmacion")
    senal = Senal.objects.create(evaluacion=evaluacion, regla=conjunto.reglas.first(), estado="no_activada", puntos=0, antecedentes=[])
    identificador = {"cierre": cierre.pk, "evaluacion": evaluacion.pk, "senal": senal.pk}[tabla]
    columna = {"cierre": "conclusion", "evaluacion": "puntaje", "senal": "puntos"}[tabla]
    valor = "'x'" if tabla == "cierre" else "99"
    for sentencia in (f"UPDATE {tabla} SET {columna} = {valor} WHERE id = %s", f"DELETE FROM {tabla} WHERE id = %s"):
        with pytest.raises(Exception):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sentencia, [identificador])


def test_cierre_valida_valoracion_y_justificacion_en_la_base():
    espacio = _espacio()
    perito = _perito(espacio)
    siniestro = _siniestro(espacio, perito)
    base = dict(siniestro=siniestro, perito=perito, resultado_reclamo="aprobado", irregularidad=False, conclusion="")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cierre.objects.create(valoracion=11, justificacion="x", **base)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cierre.objects.create(valoracion=0, justificacion="x", **base)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cierre.objects.create(valoracion=5, justificacion="", **base)


def test_cierre_existente_no_se_edita_ni_se_borra_desde_el_modelo():
    espacio = _espacio()
    perito = _perito(espacio)
    siniestro = _siniestro(espacio, perito)
    cierre = Cierre.objects.create(
        siniestro=siniestro, perito=perito, resultado_reclamo="aprobado", irregularidad=False,
        conclusion="", valoracion=7, justificacion="Justificada",
    )
    cierre.valoracion = 3
    with pytest.raises(RegistroInmutable):
        cierre.save()
    with pytest.raises(RegistroInmutable):
        cierre.delete()


def test_rs_1_0_se_crea_con_la_migracion_de_datos():
    conjunto = ConjuntoReglas.objects.get(version="RS-1.0")
    assert conjunto.activo is True
    assert str(conjunto.vigente_desde) == "2026-10-01"
    assert conjunto.topes == {
        "grupos": {"Cobertura": 30, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10},
        "total": 100,
        "prioridad": {"media": 25, "alta": 50},
    }
    reglas = {r.codigo: r for r in conjunto.reglas.all()}
    assert sorted(reglas) == ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]
    assert reglas["R01"].parametros == {"niveles": [{"max_dias": 30, "puntos": 25}, {"max_dias": 60, "puntos": 12}]}
    assert reglas["R03"].grupo == "Persona" and reglas["R03"].puntos_max == 20
    assert reglas["R08"].parametros == {"plazo_dias": 3, "puntos": 10}
    assert reglas["R07"].nombre == "Vínculo con irregularidad confirmada"


def test_solo_puede_haber_un_conjunto_activo():
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            ConjuntoReglas.objects.create(version="RS-X", vigente_desde="2026-11-01", topes={}, activo=True)


def test_el_conjunto_de_reglas_solo_permite_cambiar_el_campo_activo():
    conjunto = ConjuntoReglas.objects.get(version="RS-1.0")
    conjunto.topes = {"total": 1}
    with pytest.raises(RegistroInmutable):
        conjunto.save()
    conjunto.refresh_from_db()
    conjunto.activo = False
    conjunto.save(update_fields=["activo"])
    regla = Regla.objects.filter(conjunto=conjunto).first()
    regla.puntos_max = 1
    with pytest.raises(RegistroInmutable):
        regla.save()


def test_participacion_unica_por_siniestro_persona_y_rol():
    from nucleo.models import Participacion

    espacio = _espacio()
    perito = _perito(espacio)
    siniestro = _siniestro(espacio, perito)
    persona = Persona.objects.create(tipo_identificador="DNI", identificador="1", nombre="P")
    Participacion.objects.create(siniestro=siniestro, persona=persona, rol="asegurado")
    Participacion.objects.create(siniestro=siniestro, persona=persona, rol="conductor")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Participacion.objects.create(siniestro=siniestro, persona=persona, rol="asegurado")
