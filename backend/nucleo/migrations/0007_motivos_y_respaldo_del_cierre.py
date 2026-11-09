"""Motivos de evaluación del recálculo automático (S17) y respaldo de la irregularidad en el cierre (S18).

Agregar columnas a `cierre` no dispara los triggers de solo altas (no actualiza filas) y el rol de la
aplicación ya tiene SELECT e INSERT sobre la tabla completa.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nucleo', '0006_reglas_inmutables'),
    ]

    operations = [
        migrations.AddField(
            model_name='cierre',
            name='documentos_respaldo',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='cierre',
            name='observacion_respaldo',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AlterField(
            model_name='evaluacion',
            name='motivo',
            field=models.CharField(choices=[('confirmacion', 'Confirmación'), ('recalculo', 'Recálculo'), ('antecedente_confirmado', 'Antecedente confirmado'), ('antecedente_cerrado', 'Antecedente cerrado o con cierre modificado'), ('antecedente_archivado', 'Antecedente archivado'), ('antecedente_anulado', 'Antecedente anulado'), ('nueva_version', 'Nueva versión de reglas'), ('escenario', 'Escenario de prueba')], default='confirmacion', max_length=30),
        ),
    ]
