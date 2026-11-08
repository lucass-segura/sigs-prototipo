"""Roles de la base (F1): el rol de la aplicación no puede tocar la auditoría ni con SQL directo.

Las pruebas corren con el rol dueño (el que migra) y cambian a `DB_APP_USER` con `SET LOCAL ROLE`
dentro de un savepoint, que es lo mismo que conectarse como ese rol.
"""
import pytest
from django.conf import settings
from django.db import DatabaseError, connection, transaction

ROL_APP = settings.DB_APP_USER
APENDER = ["auditoria", "cierre", "evaluacion", "senal"]
INSERTAR_AUDITORIA = "INSERT INTO auditoria (accion, objeto, resultado, fecha, detalle) VALUES ('prueba', '', 'permitido', now(), '{}')"


@pytest.fixture(autouse=True)
def rol_de_la_aplicacion(db):
    """Las pruebas necesitan el rol de la aplicación en el clúster y poder cambiar a él."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolcreatedb FROM pg_roles WHERE rolname = %s", [ROL_APP])
        fila = cursor.fetchone()
    if fila is None:
        pytest.skip(f"No existe el rol de la aplicación {ROL_APP!r} en este PostgreSQL.")
    return ROL_APP


def como_aplicacion(sql, params=None):
    """Ejecuta `sql` con el rol de la aplicación y devuelve las filas (si hay). Usar dentro de `atomic()`."""
    with connection.cursor() as cursor:
        cursor.execute(f'SET LOCAL ROLE "{ROL_APP}"')
        cursor.execute(sql, params)
        filas = cursor.fetchall() if cursor.description else None
        cursor.execute("RESET ROLE")
        return filas


def como_dueno(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall() if cursor.description else None


def test_el_rol_de_la_aplicacion_no_es_superusuario_ni_dueno():
    assert como_dueno("SELECT rolsuper FROM pg_roles WHERE rolname = %s", [ROL_APP]) == [(False,)]
    duenos = {fila[0] for fila in como_dueno("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")}
    assert ROL_APP not in duenos
    assert como_dueno("SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()") != [(ROL_APP,)]


def test_la_aplicacion_puede_insertar_y_leer_la_auditoria():
    with transaction.atomic():
        como_aplicacion(INSERTAR_AUDITORIA)
        filas = como_aplicacion("SELECT count(*) FROM auditoria WHERE accion = 'prueba'")
    assert filas == [(1,)]


def test_la_aplicacion_opera_normalmente_en_las_tablas_comunes():
    with transaction.atomic():
        como_aplicacion("INSERT INTO espacio_trabajo (nombre, creado_en) VALUES ('Espacio de prueba', now())")
        como_aplicacion("UPDATE espacio_trabajo SET nombre = 'Otro nombre' WHERE nombre = 'Espacio de prueba'")
        assert como_aplicacion("SELECT count(*) FROM espacio_trabajo WHERE nombre = 'Otro nombre'") == [(1,)]
        como_aplicacion("DELETE FROM espacio_trabajo WHERE nombre = 'Otro nombre'")


@pytest.mark.parametrize("tabla", APENDER)
@pytest.mark.parametrize("sentencia", ["UPDATE {t} SET id = id", "DELETE FROM {t}", "TRUNCATE {t}", "TRUNCATE {t} CASCADE"])
def test_la_aplicacion_no_puede_modificar_ni_borrar_las_tablas_de_solo_altas(tabla, sentencia):
    with pytest.raises(DatabaseError, match="permission denied"), transaction.atomic():
        como_aplicacion(sentencia.format(t=tabla))


@pytest.mark.parametrize("tabla", APENDER)
@pytest.mark.parametrize("modo", ["DISABLE TRIGGER ALL", "DISABLE TRIGGER USER", f"DISABLE TRIGGER {{t}}_solo_altas", "DISABLE RULE x"])
def test_la_aplicacion_no_puede_desactivar_los_triggers(tabla, modo):
    with pytest.raises(DatabaseError, match="must be owner|permission denied"), transaction.atomic():
        como_aplicacion(f"ALTER TABLE {tabla} " + modo.format(t=tabla))


def test_la_aplicacion_no_puede_borrar_el_trigger_ni_la_tabla():
    with pytest.raises(DatabaseError, match="must be owner"), transaction.atomic():
        como_aplicacion("DROP TRIGGER auditoria_solo_altas ON auditoria")
    with pytest.raises(DatabaseError, match="must be owner"), transaction.atomic():
        como_aplicacion("DROP TABLE auditoria")


@pytest.mark.parametrize("tabla", APENDER)
def test_truncate_tambien_lo_frena_un_trigger(tabla):
    """Aun con el privilegio (el dueño lo tiene), `TRUNCATE` de una tabla de solo altas se rechaza."""
    with pytest.raises(DatabaseError, match="no se pueden modificar ni borrar"), transaction.atomic():
        como_dueno(f"TRUNCATE {tabla} CASCADE")


def test_las_tablas_nuevas_quedan_con_permisos_para_la_aplicacion():
    como_dueno("CREATE TABLE tabla_futura (id serial PRIMARY KEY, dato text)")
    assert como_dueno("SELECT has_table_privilege(%s, 'tabla_futura', 'INSERT')", [ROL_APP]) == [(True,)]
    assert como_dueno("SELECT has_sequence_privilege(%s, 'tabla_futura_id_seq', 'USAGE')", [ROL_APP]) == [(True,)]
    assert como_dueno("SELECT has_table_privilege(%s, 'tabla_futura', 'TRUNCATE')", [ROL_APP]) == [(False,)]
