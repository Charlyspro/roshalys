import os

from django.contrib.auth import get_user_model
from django.db import migrations


def set_admin_password(apps, schema_editor):
    bootstrap_password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    if not bootstrap_password:
        return

    User = get_user_model()
    admin, _ = User.objects.get_or_create(
        username="admin",
        defaults={
            "email": "admin@roshalys.local",
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    admin.email = "admin@roshalys.local"
    admin.is_staff = True
    admin.is_superuser = True
    admin.is_active = True
    admin.set_password(bootstrap_password)
    admin.save()


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0010_storehours_storeconfig"),
    ]

    operations = [
        migrations.RunPython(set_admin_password, migrations.RunPython.noop),
    ]