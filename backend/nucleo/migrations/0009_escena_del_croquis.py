from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nucleo', '0008_datos_de_la_denuncia'),
    ]

    operations = [
        migrations.AddField(
            model_name='documento',
            name='escena',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
