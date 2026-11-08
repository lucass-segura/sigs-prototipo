"""Triggers que bloquean UPDATE y DELETE en las tablas que solo admiten altas.

Protegen también contra SQL directo con el usuario de la aplicación (que no es superusuario).
"""
from django.db import migrations

TABLAS = ["auditoria", "cierre", "evaluacion", "senal"]

CREAR_FUNCION = """
CREATE OR REPLACE FUNCTION sigs_bloquear_modificacion() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'Los registros de % no se pueden modificar ni borrar.', TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;
"""

BORRAR_FUNCION = "DROP FUNCTION IF EXISTS sigs_bloquear_modificacion();"


def sentencias_directas():
    crear = [CREAR_FUNCION]
    borrar = []
    for tabla in TABLAS:
        crear.append(
            f"CREATE TRIGGER {tabla}_solo_altas BEFORE UPDATE OR DELETE ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION sigs_bloquear_modificacion();"
        )
        borrar.append(f"DROP TRIGGER IF EXISTS {tabla}_solo_altas ON {tabla};")
    crear.append("REVOKE UPDATE, DELETE ON auditoria FROM PUBLIC;")
    borrar.append("GRANT UPDATE, DELETE ON auditoria TO PUBLIC;")
    borrar.append(BORRAR_FUNCION)
    return crear, borrar


CREAR, BORRAR = sentencias_directas()


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0001_initial")]
    operations = [migrations.RunSQL(sql=CREAR, reverse_sql=BORRAR)]
