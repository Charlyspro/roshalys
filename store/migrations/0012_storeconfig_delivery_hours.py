import datetime

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0011_reset_admin_password"),
    ]

    operations = [
        migrations.AddField(
            model_name="storeconfig",
            name="delivery_from",
            field=models.TimeField(
                default=datetime.time(9, 0),
                help_text="Hora de inicio de los envíos a domicilio (fija cada día)",
                verbose_name="Domicilios: desde",
            ),
        ),
        migrations.AddField(
            model_name="storeconfig",
            name="delivery_to",
            field=models.TimeField(
                default=datetime.time(18, 0),
                help_text="Hora de fin de los envíos a domicilio (fija cada día)",
                verbose_name="Domicilios: hasta",
            ),
        ),
    ]