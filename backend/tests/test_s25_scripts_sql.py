"""S25 · Los scripts SQL de `db/sql/` no se desfasan de las migraciones.

`01_crear_base.sql` y `02_cargar_datos_demo.sql` se generan con `scripts/generar_sql.sh` desde la base real.
Estas pruebas comparan lo que dicen con la base migrada de las pruebas: si alguien agrega una tabla, un
trigger o una migración y no regenera los scripts, fallan.

Las pruebas leen `db/sql/` del repositorio. Dentro del contenedor de `backend` esa carpeta no está (la imagen
solo trae `backend/`), así que se saltean salvo que se la monte:

    docker compose run --rm -v "$PWD/db:/db:ro" backend pytest tests/test_s25_scripts_sql.py
"""
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.contrib.auth.hashers import check_password
from django.db import connection

from nucleo.constantes import CLAVE_DEMO

CARPETA = Path(__file__).resolve().parents[2] / "db" / "sql"
CREAR = CARPETA / "01_crear_base.sql"
DATOS = CARPETA / "02_cargar_datos_demo.sql"

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(not CREAR.exists(), reason="db/sql no está montada: ver la cabecera de este archivo"),
]


@pytest.fixture(scope="module")
def crear():
    return CREAR.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def datos():
    return DATOS.read_text(encoding="utf-8")


def consulta(sql):
    with connection.cursor() as cursor:
        cursor.execute(sql)
        return [fila[0] for fila in cursor.fetchall()]


# --- 01_crear_base.sql ---------------------------------------------------------------------
def test_s25_crea_los_roles_con_bloques_do_para_poder_correrse_otra_vez(crear):
    assert "CREATE ROLE sigs_owner LOGIN" in crear and "CREATE ROLE sigs_app LOGIN" in crear
    assert crear.count("IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname =") == 2
    assert "CREATE DATABASE %I OWNER sigs_owner" in crear and "WHERE NOT EXISTS (SELECT FROM pg_database" in crear


def test_s25_crea_todas_las_tablas_de_la_base_migrada(crear):
    tablas = consulta("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    assert "siniestro" in tablas and "auditoria" in tablas  # la consulta encontró el esquema
    faltan = [t for t in tablas if f"CREATE TABLE public.{t} (" not in crear]
    assert faltan == []


def test_s25_crea_las_columnas_de_los_campos_extra_de_la_denuncia(crear):
    columnas = consulta("SELECT column_name FROM information_schema.columns WHERE table_name = 'siniestro'")
    for nombre in ("numero_denuncia", "hora_denuncia", "asesor", "intervenciones", "documentacion_adjunta"):
        assert nombre in columnas
    bloque = crear.split("CREATE TABLE public.siniestro (", 1)[1].split(");", 1)[0]
    for nombre in ("numero_denuncia", "hora_denuncia", "asesor", "intervenciones", "documentacion_adjunta"):
        assert nombre in bloque


def test_s25_crea_los_triggers_las_funciones_y_los_indices_de_la_base_migrada(crear):
    triggers = consulta(
        "SELECT t.tgname FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE NOT t.tgisinternal AND n.nspname = 'public'"
    )
    assert {"auditoria_solo_altas", "auditoria_sin_truncate", "regla_inmutable", "conjunto_reglas_solo_activo"} <= set(triggers)
    assert [t for t in triggers if f"CREATE TRIGGER {t} " not in crear] == []
    funciones = consulta("SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'")
    assert "sigs_bloquear_modificacion" in funciones
    assert [f for f in funciones if f"CREATE FUNCTION public.{f}(" not in crear] == []
    indices = consulta("SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND indexname NOT LIKE '%\\_pkey'")
    assert [i for i in indices if f"INDEX {i} ON public." not in crear and f"CONSTRAINT {i} " not in crear] == []


def test_s25_otorga_al_rol_de_la_aplicacion_solo_lectura_e_insercion_en_las_tablas_de_solo_altas(crear):
    for tabla in ("auditoria", "cierre", "evaluacion", "senal"):
        assert f"GRANT SELECT,INSERT ON TABLE public.{tabla} TO sigs_app;" in crear
    assert "GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE public.siniestro TO sigs_app;" in crear
    assert "ALTER DEFAULT PRIVILEGES FOR ROLE sigs_owner IN SCHEMA public GRANT" in crear
    assert "SET ROLE sigs_owner;" in crear  # las tablas quedan a nombre del dueño, no del superusuario


def test_s25_registra_todas_las_migraciones_aplicadas(crear):
    aplicadas = consulta("SELECT app || '.' || name FROM django_migrations")
    assert "nucleo.0008_datos_de_la_denuncia" in aplicadas
    faltan = [m for m in aplicadas if f"'{m.split('.', 1)[0]}', '{m.split('.', 1)[1]}'" not in crear]
    assert faltan == []


def test_s25_carga_las_ocho_reglas_de_rs_1_0(crear):
    assert "INSERT INTO public.conjunto_reglas" in crear and "'RS-1.0'" in crear
    assert len(re.findall(r"INSERT INTO public\.regla \(", crear)) == 8
    for codigo in ("R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"):
        assert f"'{codigo}'" in crear


def test_s25_no_deja_ruido_de_pg_dump(crear, datos):
    for texto in (crear, datos):
        assert "\\restrict" not in texto and "\\unrestrict" not in texto
        assert "OWNER TO" not in texto
        assert "DISABLE TRIGGER" not in texto and "session_replication_role" not in texto


# --- 02_cargar_datos_demo.sql ---------------------------------------------------------------
def test_s25_los_datos_de_demo_no_repiten_lo_que_ya_crea_el_script_de_creacion(datos):
    for tabla in ("conjunto_reglas", "regla", "django_migrations", "django_content_type", "auth_permission"):
        assert f"INSERT INTO public.{tabla} " not in datos
    assert datos.count("BEGIN;") == 1 and datos.count("COMMIT;") == 1  # una sola transacción


def test_s32_los_datos_de_demo_anotan_la_fecha_de_generacion_para_correr_los_vencimientos(datos):
    marcas = re.findall(r"^-- generado: (\d{4}-\d{2}-\d{2})$", datos, flags=re.MULTILINE)
    assert len(marcas) == 1 and "@FECHA_GENERACION@" not in datos
    generado = date.fromisoformat(marcas[0])
    # Los vencimientos de las tareas son relativos a esa fecha: hay vencida (hoy-2), de hoy y más adelante (hoy+12)
    vencimientos = {date.fromisoformat(v) - generado for v in re.findall(r"INSERT INTO public\.tarea \(.*?VALUES \(.*?'(\d{4}-\d{2}-\d{2})'", datos)}
    assert {timedelta(days=-2), timedelta(days=0), timedelta(days=3), timedelta(days=12)} <= vencimientos


def test_s25_los_datos_de_demo_traen_a_exp_2026_0147_con_el_anexo_1(datos):
    assert "INSERT INTO public.siniestro " in datos
    for valor in ("EXP-2026-0147", "DEN-2026-0147", "Código PA-031", "Bomberos y policía", "10:20:00",
                  "DNI, cédula del vehículo, 6 fotografías y constancia de bomberos. Acta policial pendiente"):
        assert valor in datos
    assert len(re.findall(r"'ESC-[A-Z0-9]+-?[A-Z0-9]*'", datos)) >= 30


def test_s25_los_usuarios_de_demo_tienen_la_contrasena_ficticia(datos):
    hashes = re.findall(r"'(pbkdf2_sha256\$[^']+)'", datos)
    assert len(hashes) == 7  # superadmin, 2 administradores, 3 peritos y el perito de los escenarios
    assert all(check_password(CLAVE_DEMO, h) for h in hashes)
    assert "perito08@sigs.test" in datos


def test_s25_las_secuencias_quedan_ajustadas(datos):
    assert "pg_catalog.setval('public.siniestro_id_seq'" in datos
    assert "pg_catalog.setval('public.auditoria_id_seq'" in datos


def test_s25_los_documentos_de_la_demo_estan_en_el_repositorio(datos):
    referencias = re.findall(r"'(\d+/[0-9a-f]{32})'", datos)
    assert referencias, "la demo tiene al menos un documento"
    for referencia in referencias:
        archivo = CARPETA / "documentos" / referencia
        assert archivo.is_file(), f"falta db/sql/documentos/{referencia}"
