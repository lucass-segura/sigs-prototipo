"""F2: nombre de la persona, y descripción y atributos del bien, pasan a ser datos de cada caso.

`participacion.nombre`, `bien_afectado.descripcion` y `bien_afectado.atributos` son extras técnicos.
Los valores globales de `persona` y `bien` se copian a los casos que ya existen y dejan de devolverse.
"""
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def copiar_valores_globales(apps, schema_editor):
    Participacion = apps.get_model("nucleo", "Participacion")
    Persona = apps.get_model("nucleo", "Persona")
    BienAfectado = apps.get_model("nucleo", "BienAfectado")
    Bien = apps.get_model("nucleo", "Bien")
    Participacion.objects.update(
        nombre=Subquery(Persona.objects.filter(pk=OuterRef("persona_id")).values("nombre")[:1])
    )
    BienAfectado.objects.update(
        descripcion=Subquery(Bien.objects.filter(pk=OuterRef("bien_id")).values("descripcion")[:1]),
        atributos=Subquery(Bien.objects.filter(pk=OuterRef("bien_id")).values("atributos")[:1]),
    )


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0004_permisos_rol_aplicacion")]
    operations = [
        migrations.AddField(
            model_name="participacion",
            name="nombre",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
        migrations.AddField(
            model_name="bienafectado",
            name="descripcion",
            field=models.CharField(blank=True, default="", max_length=250),
        ),
        migrations.AddField(
            model_name="bienafectado",
            name="atributos",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(copiar_valores_globales, migrations.RunPython.noop),
    ]
