"""Permisos del rol de la aplicación y `TRUNCATE` bloqueado en las tablas de solo altas.

Se aplica después de los triggers de `0002`. La base la crea y la migra el rol dueño; la aplicación
corre con `DB_APP_USER`, que no es dueño ni superusuario:

- tablas comunes: SELECT, INSERT, UPDATE y DELETE; secuencias: USAGE y SELECT;
- `auditoria`, `cierre`, `evaluacion` y `senal`: solo SELECT e INSERT. Sin UPDATE, DELETE ni TRUNCATE, y
  como no es dueño tampoco puede desactivar ni borrar los triggers (`ALTER TABLE ... DISABLE TRIGGER`).

Si el rol no existe (por ejemplo, una base armada sin el script `db/init`) los permisos se omiten, pero
el trigger de `TRUNCATE` se crea igual. Las tablas que se creen en migraciones futuras heredan los permisos
comunes por `ALTER DEFAULT PRIVILEGES`: si son de solo altas, la migración tiene que revocar el resto.
"""
from django.conf import settings
from django.db import migrations

TABLAS_SOLO_ALTAS = ["auditoria", "cierre", "evaluacion", "senal"]


def _sin_truncate():
    crear, borrar = [], []
    for tabla in TABLAS_SOLO_ALTAS:
        crear.append(
            f"CREATE TRIGGER {tabla}_sin_truncate BEFORE TRUNCATE ON {tabla} "
            "FOR EACH STATEMENT EXECUTE FUNCTION sigs_bloquear_modificacion();"
        )
        borrar.append(f"DROP TRIGGER IF EXISTS {tabla}_sin_truncate ON {tabla};")
    return crear, borrar


def _rol_de_la_aplicacion(conexion, cursor):
    """Nombre del rol ya citado, o `None` si no existe en este PostgreSQL."""
    cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [settings.DB_APP_USER])
    if cursor.fetchone() is None:
        return None
    return conexion.ops.quote_name(settings.DB_APP_USER)


def otorgar_permisos(apps, schema_editor):
    conexion = schema_editor.connection
    with conexion.cursor() as cursor:
        rol = _rol_de_la_aplicacion(conexion, cursor)
        if rol is None:
            return
        tablas = ", ".join(TABLAS_SOLO_ALTAS)
        sentencias = [
            f"GRANT USAGE ON SCHEMA public TO {rol}",
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rol}",
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {rol}",
            f"REVOKE UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER ON {tablas} FROM {rol}",
            f"REVOKE UPDATE, DELETE, TRUNCATE ON {tablas} FROM PUBLIC",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rol}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {rol}",
        ]
        for sentencia in sentencias:
            cursor.execute(sentencia)


def quitar_permisos(apps, schema_editor):
    conexion = schema_editor.connection
    with conexion.cursor() as cursor:
        rol = _rol_de_la_aplicacion(conexion, cursor)
        if rol is None:
            return
        for sentencia in (
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {rol}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {rol}",
            f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {rol}",
            f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {rol}",
        ):
            cursor.execute(sentencia)


CREAR, BORRAR = _sin_truncate()


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0003_reglas_rs_1_0")]
    operations = [
        migrations.RunSQL(sql=CREAR, reverse_sql=BORRAR),
        migrations.RunPython(otorgar_permisos, quitar_permisos),
    ]
