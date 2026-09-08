import datetime

from django.db import migrations, models


def create_defaults(apps, schema_editor):
    StoreHours = apps.get_model("store", "StoreHours")
    StoreConfig = apps.get_model("store", "StoreConfig")
    for day in range(5):
        StoreHours.objects.create(
            day=day,
            open_time=datetime.time(9, 0),
            close_time=datetime.time(18, 0),
            is_closed=False,
        )
    StoreHours.objects.create(
        day=5,
        open_time=datetime.time(9, 0),
        close_time=datetime.time(13, 0),
        is_closed=False,
    )
    StoreHours.objects.create(day=6, open_time=None, close_time=None, is_closed=True)
    StoreConfig.objects.get_or_create(pk=1, defaults={"force_open": False})


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0009_normalize_category_slugs"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoreConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "force_open",
                    models.BooleanField(
                        default=False,
                        help_text="Marca para forzar la tienda abierta (emergencias, ferias, etc.)",
                        verbose_name="Forzar tienda abierta",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración de la tienda",
                "verbose_name_plural": "Configuración de la tienda",
            },
        ),
        migrations.CreateModel(
            name="StoreHours",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "day",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (0, "Lunes"),
                            (1, "Martes"),
                            (2, "Miércoles"),
                            (3, "Jueves"),
                            (4, "Viernes"),
                            (5, "Sábado"),
                            (6, "Domingo"),
                        ],
                        unique=True,
                        verbose_name="Día",
                    ),
                ),
                (
                    "open_time",
                    models.TimeField(blank=True, null=True, verbose_name="Apertura"),
                ),
                (
                    "close_time",
                    models.TimeField(blank=True, null=True, verbose_name="Cierre"),
                ),
                (
                    "is_closed",
                    models.BooleanField(default=False, verbose_name="Cerrado"),
                ),
            ],
            options={
                "verbose_name": "Horario",
                "verbose_name_plural": "Horarios",
                "ordering": ["day"],
            },
        ),
        migrations.RunPython(create_defaults, migrations.RunPython.noop),
    ]