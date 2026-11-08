"""Triggers que fijan las reglas publicadas (HU-12): una versión no se edita, se publica otra.

- `regla`: no admite UPDATE ni DELETE.
- `conjunto_reglas`: no admite DELETE y de un UPDATE solo se acepta el cambio de `activo`
  (al publicar una versión nueva, la anterior deja de estar activa).

Valen también para SQL directo: el rol de la aplicación no es dueño de las tablas y no puede quitarlos.
"""
from django.db import migrations

CREAR = [
    """
    CREATE OR REPLACE FUNCTION sigs_conjunto_solo_activo() RETURNS trigger AS $$
    BEGIN
        IF (to_jsonb(NEW) - 'activo') IS DISTINCT FROM (to_jsonb(OLD) - 'activo') THEN
            RAISE EXCEPTION 'Un conjunto de reglas publicado solo puede cambiar el campo activo.'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """,
    "CREATE TRIGGER regla_inmutable BEFORE UPDATE OR DELETE ON regla "
    "FOR EACH ROW EXECUTE FUNCTION sigs_bloquear_modificacion();",
    "CREATE TRIGGER conjunto_reglas_sin_borrado BEFORE DELETE ON conjunto_reglas "
    "FOR EACH ROW EXECUTE FUNCTION sigs_bloquear_modificacion();",
    "CREATE TRIGGER conjunto_reglas_solo_activo BEFORE UPDATE ON conjunto_reglas "
    "FOR EACH ROW EXECUTE FUNCTION sigs_conjunto_solo_activo();",
]

BORRAR = [
    "DROP TRIGGER IF EXISTS conjunto_reglas_solo_activo ON conjunto_reglas;",
    "DROP TRIGGER IF EXISTS conjunto_reglas_sin_borrado ON conjunto_reglas;",
    "DROP TRIGGER IF EXISTS regla_inmutable ON regla;",
    "DROP FUNCTION IF EXISTS sigs_conjunto_solo_activo();",
]


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0005_datos_por_caso")]
    operations = [migrations.RunSQL(sql=CREAR, reverse_sql=BORRAR)]
