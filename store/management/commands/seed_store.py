from django.core.management.base import BaseCommand

from store.models import Category, Product


class Command(BaseCommand):
    help = "Carga datos de ejemplo para ROSHALYS"

    def handle(self, *args, **options):
        category_electronics, _ = Category.objects.get_or_create(
            slug="electronica",
            defaults={"name": "Electrónica"},
        )
        category_home, _ = Category.objects.get_or_create(
            slug="hogar",
            defaults={"name": "Hogar"},
        )
        category_accessories, _ = Category.objects.get_or_create(
            slug="accesorios",
            defaults={"name": "Accesorios"},
        )

        product_data = [
            {
                "category": category_electronics,
                "name": "Smartphone",
                "slug": "smartphone",
                "description": "Teléfono inteligente de demostración.",
                "price": 250.00,
                "stock": 12,
                "is_featured": True,
            },
            {
                "category": category_home,
                "name": "Lampara LED",
                "slug": "lampara-led",
                "description": "Luz moderna para mesas y rincones.",
                "price": 79.99,
                "stock": 8,
                "is_featured": True,
            },
            {
                "category": category_accessories,
                "name": "Auriculares Bluetooth",
                "slug": "auriculares-bluetooth",
                "description": "Audio inalámbrico con gran autonomía.",
                "price": 135.50,
                "stock": 15,
                "is_featured": False,
            },
            {
                "category": category_electronics,
                "name": "Tablet Pro",
                "slug": "tablet-pro",
                "description": "Tablet ligera y rápida para estudio y entretenimiento.",
                "price": 390.00,
                "stock": 6,
                "is_featured": True,
            },
        ]

        for item in product_data:
            Product.objects.update_or_create(
                slug=item["slug"],
                defaults=item,
            )

        self.stdout.write(self.style.SUCCESS("Datos de ejemplo cargados con éxito."))
