from django.db import migrations
from django.utils.text import slugify


def normalize_category_slugs(apps, schema_editor):
    Category = apps.get_model("store", "Category")
    used = set()
    for category in Category.objects.all().order_by("id"):
        base = slugify(category.name) or slugify(category.slug) or "categoria"
        new_slug = base
        counter = 2
        while new_slug in used:
            new_slug = f"{base}-{counter}"
            counter += 1
        used.add(new_slug)
        if category.slug != new_slug:
            category.slug = new_slug
            category.save(update_fields=["slug"])


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0008_delete_productdeliveryconfig"),
    ]

    operations = [
        migrations.RunPython(normalize_category_slugs, migrations.RunPython.noop),
    ]