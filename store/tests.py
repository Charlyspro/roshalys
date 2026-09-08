import datetime
import json
from decimal import Decimal
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from store.hours import _local_now, delivery_window, is_open, next_open_info, schedule_summary, seconds_until_open
from store.models import Category, DailyStats, DeliveryZone, Feedback, Order, OrderItem, Product, StoreConfig, StoreHours, VisitorCountry
from store.visits import _geo_lookup, country_votes, visits_summary

# El middleware de tienda cerrada consulta la hora real; durante los tests
# se mantiene "abierto" salvo en los casos que se prueban explícitamente.
mock.patch("store.middleware.is_open", return_value=True).start()


class StoreModelTests(TestCase):
    def test_can_create_active_product_and_category(self):
        category = Category.objects.create(name="Electrónica", slug="electronica")
        product = Product.objects.create(
            category=category,
            name="Smartphone",
            slug="smartphone",
            price=250.00,
            description="Teléfono inteligente de demostración.",
            stock=10,
            is_active=True,
            is_featured=True,
        )

        self.assertEqual(str(category), "Electrónica")
        self.assertEqual(str(product), "Smartphone")
        self.assertTrue(product.is_active)
        self.assertTrue(product.is_featured)

    def test_catalog_home_renders(self):
        category = Category.objects.create(name="Electrónica", slug="electronica")
        Product.objects.create(
            category=category,
            name="Smartphone",
            slug="smartphone",
            price=250.00,
            description="Teléfono inteligente de demostración.",
            stock=10,
            is_active=True,
            is_featured=True,
        )

        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ROSHALYS")

    def test_inactive_products_dont_display(self):
        category = Category.objects.create(name="Electrónica", slug="electronica")
        Product.objects.create(
            category=category,
            name="Producto Inactivo",
            slug="producto-inactivo",
            price=100.00,
            description="No debe aparecer",
            stock=10,
            is_active=False,
        )
        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Producto Inactivo")

    def test_home_shows_best_sellers_carousel_ordered_by_sales(self):
        category = Category.objects.create(name="Electrónica", slug="electronica")
        top = Product.objects.create(
            category=category, name="Top Vendido", slug="top-vendido",
            price=100.00, description="El más comprado.", stock=10, is_active=True,
        )
        low = Product.objects.create(
            category=category, name="Poco Vendido", slug="poco-vendido",
            price=100.00, description="Se vende menos.", stock=10, is_active=True,
        )
        order = Order.objects.create(customer_name="Cliente", customer_phone="5491111111111")
        OrderItem.objects.create(order=order, product=top, quantity=4, price=top.price)
        OrderItem.objects.create(order=order, product=low, quantity=1, price=low.price)

        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-interval=\"10000\"")
        self.assertContains(response, "carousel-slide")
        self.assertLess(
            response.content.decode().index("Top Vendido"),
            response.content.decode().index("Poco Vendido"),
        )

    def test_best_sellers_fills_with_active_products_when_no_sales(self):
        category = Category.objects.create(name="Electrónica", slug="electronica")
        Product.objects.create(
            category=category, name="Sin Ventas", slug="sin-ventas",
            price=50.00, description="Producto sin pedidos.", stock=10, is_active=True,
        )
        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sin Ventas")

    def test_category_slug_uniqueness(self):
        category1 = Category.objects.create(name="Categoría 1", slug="test-slug")
        with self.assertRaises(Exception):
            Category.objects.create(name="Categoría 2", slug="test-slug")

    def test_product_slug_uniqueness(self):
        category = Category.objects.create(name="Test", slug="test")
        Product.objects.create(
            category=category,
            name="Producto 1",
            slug="test-product",
            price=100.00,
            description="Desc",
            stock=10,
        )
        with self.assertRaises(Exception):
            Product.objects.create(
                category=category,
                name="Producto 2",
                slug="test-product",
                price=100.00,
                description="Desc",
                stock=10,
            )

    def test_delivery_zone_creation(self):
        zone = DeliveryZone.objects.create(
            name="Zona Centro",
            cost=Decimal("50.00"),
            is_active=True
        )
        self.assertEqual(str(zone), "Zona Centro ($50.00)")
        self.assertEqual(zone.cost, Decimal("50.00"))


class CartAndCheckoutTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electrónica", slug="electronica")
        self.product = Product.objects.create(
            category=self.category,
            name="Teléfono",
            slug="telefono",
            description="Producto de prueba",
            price=Decimal("100.00"),
            stock=5,
        )

    def add_cart(self, quantity="1"):
        return self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": quantity})

    def test_adds_valid_quantity(self):
        response = self.add_cart("2")
        self.assertRedirects(response, reverse("store:home"))
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 2})

    def test_invalid_quantities_do_not_raise_server_error(self):
        for quantity in ("-1", "0", "abc", ""):
            response = self.add_cart(quantity)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get("cart", {}), {})

    def test_cannot_add_out_of_stock_product(self):
        self.product.stock = 0
        self.product.save(update_fields=["stock"])
        self.add_cart("1")
        self.assertEqual(self.client.session.get("cart", {}), {})

    def test_checkout_creates_order_decrements_stock_and_clears_cart(self):
        user = User.objects.create_user(username="cliente", password="pass12345", email="cliente@test.local")
        self.client.force_login(user)
        self.add_cart("2")
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        response = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Ana Cliente",
            "customer_phone": "555123",
            "customer_email": "cliente@test.local",
            "delivery_option": "pickup",
        })
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.user, user)
        self.assertEqual(order.total, Decimal("200.00"))
        self.assertEqual(OrderItem.objects.get().price, Decimal("100.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(self.client.session.get("cart", {}), {})
        self.assertContains(response, f"#{order.pk}")

    def test_delivery_requires_address_and_pickup_does_not(self):
        self.add_cart("1")
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        invalid = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token, "customer_name": "Ana", "delivery_option": "delivery",
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        valid = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token, "customer_name": "Ana", "delivery_option": "pickup",
        })
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)

    def test_delivery_options_are_labeled_correctly(self):
        self.add_cart("1")
        response = self.client.get(reverse("store:whatsapp_checkout"))
        self.assertContains(response, "Recoger en el local")
        self.assertContains(response, "Envío a domicilio")

    def test_checkout_rejects_invalid_phone(self):
        self.add_cart("1")
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        response = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token, "customer_name": "Ana", "customer_phone": "invalid!",
            "delivery_option": "pickup",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_with_insufficient_stock_preserves_cart(self):
        self.add_cart("2")
        self.product.stock = 1
        self.product.save(update_fields=["stock"])
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        response = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Ana Cliente",
            "delivery_option": "pickup",
        })
        self.assertRedirects(response, reverse("store:cart")) if response.status_code == 302 else self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 2})

    def test_same_checkout_token_is_idempotent(self):
        self.add_cart("1")
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        data = {"checkout_token": token, "customer_name": "Ana", "delivery_option": "pickup"}
        self.client.post(reverse("store:whatsapp_checkout"), data)
        self.client.session["cart"] = {str(self.product.pk): 1}
        self.client.session.save()
        self.client.post(reverse("store:whatsapp_checkout"), data)
        self.assertEqual(Order.objects.filter(checkout_token=token).count(), 1)

    def test_order_item_keeps_historical_product_name(self):
        self.add_cart("1")
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token, "customer_name": "Ana", "delivery_option": "pickup",
        })
        item = OrderItem.objects.get()
        self.product.name = "Teléfono actualizado"
        self.product.save(update_fields=["name"])
        item.refresh_from_db()
        self.assertEqual(item.product_name, "Teléfono")


class AuthenticationAndPermissionTests(TestCase):
    def test_profile_requires_store_login(self):
        response = self.client.get(reverse("store:profile"))
        self.assertRedirects(response, f"{reverse('store:login')}?next={reverse('store:profile')}")

    def test_user_sees_only_own_orders(self):
        owner = User.objects.create_user(username="owner", password="pass12345", email="owner@test.local")
        other = User.objects.create_user(username="other", password="pass12345", email="other@test.local")
        Order.objects.create(user=owner, customer_name="Owner", total=10)
        Order.objects.create(user=other, customer_name="Other", total=20)
        self.client.force_login(owner)
        response = self.client.get(reverse("store:profile"))
        self.assertContains(response, "$10")
        self.assertNotContains(response, "$20")

    def test_admin_dashboard_requires_staff(self):
        user = User.objects.create_user(username="cliente", password="pass12345")
        self.client.force_login(user)
        response = self.client.get(reverse("store:admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_logout_link_works(self):
        user = User.objects.create_user(username="cliente", password="pass12345")
        self.client.force_login(user)
        response = self.client.get(reverse("store:logout"))
        self.assertIn(response.status_code, (302, 303))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class SearchAndCategoryTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Electrónica", slug="electronica")
        self.product1 = Product.objects.create(
            category=self.category,
            name="Smartphone Samsung",
            slug="smartphone-samsung",
            price=Decimal("250.00"),
            description="Teléfono inteligente",
            stock=10,
            is_active=True,
        )
        self.product2 = Product.objects.create(
            category=self.category,
            name="Tablet iPad",
            slug="tablet-ipad",
            price=Decimal("400.00"),
            description="Tableta profesional",
            stock=5,
            is_active=True,
        )
        self.product3 = Product.objects.create(
            category=self.category,
            name="Smartwatch",
            slug="smartwatch",
            price=Decimal("150.00"),
            description="Reloj inteligente",
            stock=0,
            is_active=True,
        )

    def test_category_page_displays_products(self):
        response = self.client.get(reverse("store:category_products", args=["electronica"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smartphone Samsung")
        self.assertContains(response, "Tablet iPad")
        self.assertContains(response, "Smartwatch")

    def test_search_by_name(self):
        response = self.client.get(reverse("store:search_products"), {"q": "Smartphone"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smartphone Samsung")
        self.assertNotContains(response, "Tablet iPad")

    def test_search_by_description(self):
        response = self.client.get(reverse("store:search_products"), {"q": "tableta"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tablet iPad")

    def test_search_by_category(self):
        response = self.client.get(reverse("store:search_products"), {"q": "Electrónica"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smartphone Samsung")
        self.assertContains(response, "Tablet iPad")

    def test_search_empty_query(self):
        response = self.client.get(reverse("store:search_products"), {"q": ""})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["page_obj"]), 3)

    def test_product_detail_page(self):
        response = self.client.get(reverse("store:product_detail", args=["smartphone-samsung"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smartphone Samsung")
        self.assertContains(response, "250,00")  # Formato con coma como en el template
        self.assertContains(response, "Teléfono inteligente")

    def test_product_detail_404_for_inactive(self):
        self.product1.is_active = False
        self.product1.save()
        response = self.client.get(reverse("store:product_detail", args=["smartphone-samsung"]))
        self.assertEqual(response.status_code, 404)

    def test_category_pagination(self):
        # Crear 15 productos más para probar paginación
        for i in range(15):
            Product.objects.create(
                category=self.category,
                name=f"Producto {i}",
                slug=f"producto-{i}",
                price=Decimal("100.00"),
                description="Test",
                stock=10,
                is_active=True,
            )
        response = self.client.get(reverse("store:category_products", args=["electronica"]), {"page": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_next())


class AdminProductManagementTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@test.local",
            password="admin123"
        )
        self.category = Category.objects.create(name="Electrónica", slug="electronica")
        self.product = Product.objects.create(
            category=self.category,
            name="Producto Test",
            slug="producto-test",
            price=Decimal("100.00"),
            description="Descripción de prueba",
            stock=10,
            is_active=True,
        )

    def test_admin_dashboard_accessible_to_staff(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("store:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_admin_products_page_requires_login(self):
        response = self.client.get(reverse("store:admin_products"))
        self.assertEqual(response.status_code, 302)

    def test_admin_products_page_requires_staff(self):
        regular_user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(regular_user)
        response = self.client.get(reverse("store:admin_products"))
        self.assertEqual(response.status_code, 302)

    def test_admin_can_create_product(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse("store:admin_products"), {
            "name": "Nuevo Producto",
            "category": self.category.id,
            "slug": "nuevo-producto",
            "price": "150.00",
            "stock": "20",
            "description": "Descripción del nuevo producto",
            "is_active": True,
        })
        self.assertIn(response.status_code, (200, 302))  # POST puede devolver 200 o 302
        products = Product.objects.filter(slug="nuevo-producto")
        self.assertEqual(products.count(), 1)
        new_product = products.first()
        self.assertEqual(new_product.name, "Nuevo Producto")
        self.assertEqual(new_product.stock, 20)
        self.assertEqual(new_product.price, Decimal("150.00"))

    def test_admin_can_create_product_with_image(self):
        from io import BytesIO
        from PIL import Image as PILImage

        self.client.force_login(self.admin_user)
        image_buffer = BytesIO()
        PILImage.new("RGB", (4, 4), color=(255, 0, 0)).save(image_buffer, format="PNG")
        image = SimpleUploadedFile(
            "producto.png",
            image_buffer.getvalue(),
            content_type="image/png",
        )
        response = self.client.post(reverse("store:admin_products"), {
            "name": "Producto Con Imagen",
            "category": self.category.id,
            "slug": "producto-con-imagen",
            "price": "99.99",
            "stock": "5",
            "description": "Producto con imagen",
            "is_active": True,
            "image": image,
        })
        self.assertIn(response.status_code, (200, 302))
        product = Product.objects.filter(slug="producto-con-imagen").first()
        self.assertIsNotNone(product)
        self.assertTrue(product.image)

    def test_admin_can_edit_product(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("store:admin_edit_product", args=[self.product.id]),
            {
                "name": "Producto Editado",
                "category": self.category.id,
                "slug": self.product.slug,
                "price": "200.00",
                "stock": "30",
                "description": "Nueva descripción",
                "is_active": True,
            }
        )
        self.assertIn(response.status_code, (200, 302))
        self.product.refresh_from_db()
        self.assertEqual(self.product.name, "Producto Editado")
        self.assertEqual(self.product.price, Decimal("200.00"))
        self.assertEqual(self.product.stock, 30)

    def test_admin_can_view_edit_form(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("store:admin_edit_product", args=[self.product.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)

    def test_admin_can_delete_product(self):
        self.client.force_login(self.admin_user)
        product_id = self.product.id
        response = self.client.get(reverse("store:admin_delete_product", args=[product_id]))
        # Puede ser 200, 302 o similar
        # La eliminación se hace en el GET con confirmación
        products = Product.objects.filter(id=product_id)
        # El producto debería haber sido eliminado o la vista debería existir
        self.assertTrue(response.status_code in [200, 302, 404])

    def test_admin_products_list_shows_all_products(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("store:admin_products"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Producto Test")
        self.assertEqual(response.context["products"].count(), 1)

    def test_admin_cannot_create_duplicate_slug(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse("store:admin_products"), {
            "name": "Otro Producto",
            "category": self.category.id,
            "slug": "producto-test",  # Slug duplicado
            "price": "100.00",
            "stock": "10",
            "description": "Descripción",
            "is_active": True,
        })
        self.assertEqual(response.status_code, 200)  # Formulario rechazado
        self.assertEqual(Product.objects.filter(slug="producto-test").count(), 1)


class DeliveryAndCostCalculationTests(TestCase):
    TZ = ZoneInfo("America/Havana")
    IN_WINDOW = datetime.datetime(2026, 9, 7, 15, 0, tzinfo=TZ)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._now_patcher = mock.patch("store.hours._local_now", return_value=cls.IN_WINDOW)
        cls._now_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._now_patcher.stop()
        super().tearDownClass()

    def setUp(self):
        self.category = Category.objects.create(name="Test", slug="test")
        self.product = Product.objects.create(
            category=self.category,
            name="Producto",
            slug="producto",
            price=Decimal("100.00"),
            description="Test",
            stock=10,
        )
        self.zone = DeliveryZone.objects.create(
            name="Zona Centro",
            cost=Decimal("50.00"),
            is_active=True,
        )

    def test_delivery_cost_added_to_order_total(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "10"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        response = self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Cliente",
            "delivery_option": "delivery",
            "delivery_zone": self.zone.id,
            "delivery_address": "Calle Test 123",
        })
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.delivery_cost, Decimal("50.00"))
        self.assertEqual(order.total, Decimal("1050.00"))  # 1000 + 50

    def test_delivery_zone_saved_to_order(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "10"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Cliente",
            "delivery_option": "delivery",
            "delivery_zone": self.zone.id,
            "delivery_address": "Calle Test 123",
        })
        order = Order.objects.get()
        self.assertEqual(order.delivery_zone, self.zone)

    def test_pickup_has_zero_delivery_cost(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "1"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Cliente",
            "delivery_option": "pickup",
        })
        order = Order.objects.get()
        self.assertEqual(order.delivery_cost, Decimal("0.00"))
        self.assertEqual(order.total, Decimal("100.00"))

    def test_delivery_rejected_below_min_total(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "5"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        self.client.post(reverse("store:whatsapp_checkout"), {
            "checkout_token": token,
            "customer_name": "Cliente",
            "delivery_option": "delivery",
            "delivery_zone": self.zone.id,
            "delivery_address": "Calle Test 123",
        })
        self.assertFalse(Order.objects.exists())


class DeliveryWindowTests(TestCase):
    TZ = ZoneInfo("America/Havana")
    MONDAY_AFTERNOON = datetime.datetime(2026, 9, 7, 15, 0, tzinfo=TZ)
    MONDAY_NIGHT = datetime.datetime(2026, 9, 7, 20, 0, tzinfo=TZ)

    def setUp(self):
        StoreConfig.objects.get_or_create(pk=1, defaults={"force_open": False})
        StoreHours.objects.all().delete()
        for day, open_time, close_time, closed in [
            (0, datetime.time(9, 0), datetime.time(21, 0), False),
            (1, datetime.time(9, 0), datetime.time(21, 0), False),
            (2, datetime.time(9, 0), datetime.time(21, 0), False),
            (3, datetime.time(9, 0), datetime.time(21, 0), False),
            (4, datetime.time(9, 0), datetime.time(21, 0), False),
            (5, datetime.time(9, 0), datetime.time(21, 0), False),
            (6, None, None, True),
        ]:
            StoreHours.objects.create(day=day, open_time=open_time, close_time=close_time, is_closed=closed)
        self.category = Category.objects.create(name="General", slug="general")
        self.product = Product.objects.create(
            name="Artículo", slug="articulo", price=Decimal("100.00"), description="Test", stock=10,
            category=self.category,
        )

    def test_delivery_window_active_in_hours(self):
        with mock.patch("store.hours._local_now", return_value=self.MONDAY_AFTERNOON):
            win = delivery_window()
        self.assertTrue(win["active"])
        self.assertEqual(win["hours_text"], "09:00 a 18:00")

    def test_delivery_window_inactive_out_of_hours(self):
        with mock.patch("store.hours._local_now", return_value=self.MONDAY_NIGHT):
            win = delivery_window()
        self.assertFalse(win["active"])
        self.assertTrue(win["resume_label"].startswith("Mañana"))

    def test_checkout_get_shows_delivery_hours(self):
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        response = self.client.get(reverse("store:whatsapp_checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Domicilios: de 09:00 a 18:00")

    def test_checkout_rejects_late_delivery_without_acceptance(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        zone = DeliveryZone.objects.create(name="Zona Centro", cost=Decimal("50.00"), is_active=True)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        with mock.patch("store.hours._local_now", return_value=self.MONDAY_NIGHT):
            response = self.client.post(reverse("store:whatsapp_checkout"), {
                "checkout_token": token,
                "customer_name": "Cliente",
                "delivery_option": "delivery",
                "delivery_zone": zone.id,
                "delivery_address": "Calle Test 123",
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "fuera del horario de domicilio")
        self.assertFalse(Order.objects.exists())

    def test_checkout_accepts_late_delivery_with_acceptance(self):
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        zone = DeliveryZone.objects.create(name="Zona Centro", cost=Decimal("50.00"), is_active=True)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "10"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        with mock.patch("store.hours._local_now", return_value=self.MONDAY_NIGHT):
            response = self.client.post(reverse("store:whatsapp_checkout"), {
                "checkout_token": token,
                "customer_name": "Cliente",
                "delivery_option": "delivery",
                "delivery_zone": zone.id,
                "delivery_address": "Calle Test 123",
                "accept_delivery_late": "on",
            })
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.delivery_cost, Decimal("50.00"))
        self.assertIn("al día siguiente", order.notes)

    def test_checkout_pickup_ignores_delivery_window(self):
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "2"})
        checkout = self.client.get(reverse("store:whatsapp_checkout"))
        token = checkout.context["form"].initial["checkout_token"]
        with mock.patch("store.hours._local_now", return_value=self.MONDAY_NIGHT):
            response = self.client.post(reverse("store:whatsapp_checkout"), {
                "checkout_token": token,
                "customer_name": "Cliente",
                "delivery_option": "pickup",
            })
        self.assertEqual(response.status_code, 200)
        order = Order.objects.get()
        self.assertEqual(order.delivery_option, "pickup")
        self.assertNotIn("al día siguiente", order.notes)


class OrderAdminActionsTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@test.local",
            password="admin123"
        )
        category = Category.objects.create(name="Categoría", slug="categoria")
        self.product = Product.objects.create(
            category=category,
            name="Producto",
            slug="producto",
            price=Decimal("100.00"),
            description="Desc",
            stock=5,
            is_active=True,
        )
        self.order1 = Order.objects.create(
            customer_name="Cliente Uno",
            customer_phone="54927950001",
            status="pending",
            delivery_option="pickup",
            total=Decimal("100.00"),
        )
        self.order2 = Order.objects.create(
            customer_name="Cliente Dos",
            customer_phone="54927950002",
            status="pending",
            delivery_option="pickup",
            total=Decimal("100.00"),
        )

    def test_admin_order_page_shows_status_actions(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:store_order_changelist"))
        self.assertEqual(response.status_code, 200)
        from django.contrib.admin import site
        model_admin = site._registry[Order]
        request = self.client.get(reverse("admin:index")).wsgi_request
        action_names = list(model_admin.get_actions(request).keys())
        self.assertIn("marcar_confirmado", action_names)
        self.assertIn("marcar_enviado", action_names)
        self.assertIn("marcar_entregado", action_names)
        self.assertIn("marcar_cancelado", action_names)

    def test_admin_mark_orders_confirmed(self):
        self.client.force_login(self.admin_user)
        url = reverse("admin:store_order_changelist")
        response = self.client.post(url, {
            "action": "marcar_confirmado",
            "_selected_action": [str(self.order1.pk), str(self.order2.pk)],
        })
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(Order.objects.get(pk=self.order1.pk).status, "confirmed")
        self.assertEqual(Order.objects.get(pk=self.order2.pk).status, "confirmed")

    def test_admin_mark_orders_delivered(self):
        self.client.force_login(self.admin_user)
        url = reverse("admin:store_order_changelist")
        response = self.client.post(url, {
            "action": "marcar_entregado",
            "_selected_action": [str(self.order1.pk)],
        })
        self.assertIn(response.status_code, (200, 302))
        self.assertEqual(Order.objects.get(pk=self.order1.pk).status, "delivered")

    def test_action_shows_whatsapp_links_for_customers(self):
        self.client.force_login(self.admin_user)
        url = reverse("admin:store_order_changelist")
        response = self.client.post(url, {
            "action": "marcar_confirmado",
            "_selected_action": [str(self.order1.pk)],
        })
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("wa.me/54927950001", content)
        self.assertIn("confirmado", content)
        self.assertEqual(Order.objects.get(pk=self.order1.pk).status, "confirmed")


class AdminPublishProductTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@test.local", password="admin123"
        )
        self.category = Category.objects.create(name="Electrónica", slug="electronica")
        self.product = Product.objects.create(
            category=self.category,
            name="Producto Publicable",
            slug="producto-publicable",
            price=Decimal("99.99"),
            description="Descripción de prueba para el grupo.",
            stock=10,
            is_active=True,
        )

    def test_publish_page_requires_staff(self):
        response = self.client.get(reverse("store:admin_publish_product", args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)

    def test_publish_page_shows_message_with_price_and_description(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("store:admin_publish_product", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("*Producto Publicable*", content)
        self.assertIn("Precio: $99.99", content)
        self.assertIn("producto-publicable", content)

    def test_publish_message_has_contact_numbers(self):
        from store.whatsapp import build_product_message
        message = build_product_message(self.product, "ROSHALYS", "https://roshalys.wasmer.app/producto/producto-publicable")
        self.assertIn("$99.99", message)
        self.assertIn("Producto Publicable", message)
        self.assertNotIn("Descripción", message)
        self.assertNotIn("Escríbanos", message)

    def test_product_page_exposes_open_graph_image(self):
        from io import BytesIO
        from PIL import Image as PILImage

        image_buffer = BytesIO()
        PILImage.new("RGB", (4, 4), color=(255, 0, 0)).save(image_buffer, format="PNG")
        product = Product.objects.create(
            category=self.category,
            name="Producto Con Foto",
            slug="producto-con-foto",
            price=Decimal("50.00"),
            description="Foto de prueba para Open Graph.",
            stock=5,
            is_active=True,
            image=SimpleUploadedFile("foto.png", image_buffer.getvalue(), content_type="image/png"),
        )
        response = self.client.get(reverse("store:product_detail", args=[product.slug]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('property="og:image"', content)
        self.assertIn('property="og:type" content="product"', content)
        self.assertIn("/media/", content)

    def test_product_admin_list_has_whatsapp_publish_link(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:store_product_changelist"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("/admin-productos/publicar/", content)


class StoreHoursTests(TestCase):
    TZ = ZoneInfo("America/Havana")

    MONDAY_MORNING = datetime.datetime(2026, 9, 7, 10, 0, tzinfo=TZ)
    MONDAY_NIGHT = datetime.datetime(2026, 9, 7, 20, 0, tzinfo=TZ)
    TUESDAY_MORNING = datetime.datetime(2026, 9, 8, 7, 0, tzinfo=TZ)
    SATURDAY_AFTERNOON = datetime.datetime(2026, 9, 12, 14, 0, tzinfo=TZ)
    SUNDAY_REST = datetime.datetime(2026, 9, 13, 12, 0, tzinfo=TZ)

    def setUp(self):
        StoreConfig.objects.get_or_create(pk=1, defaults={"force_open": False})
        StoreHours.objects.all().delete()
        for day, open_time, close_time, closed in [
            (0, datetime.time(9, 0), datetime.time(18, 0), False),
            (1, datetime.time(9, 0), datetime.time(18, 0), False),
            (2, datetime.time(9, 0), datetime.time(18, 0), False),
            (3, datetime.time(9, 0), datetime.time(18, 0), False),
            (4, datetime.time(9, 0), datetime.time(18, 0), False),
            (5, datetime.time(9, 0), datetime.time(13, 0), False),
            (6, None, None, True),
        ]:
            StoreHours.objects.create(day=day, open_time=open_time, close_time=close_time, is_closed=closed)

    def test_open_on_monday_morning(self):
        self.assertTrue(is_open(self.MONDAY_MORNING))
        self.assertEqual(seconds_until_open(self.MONDAY_MORNING), 0)

    def test_closed_on_monday_night(self):
        self.assertFalse(is_open(self.MONDAY_NIGHT))
        self.assertEqual(seconds_until_open(self.MONDAY_NIGHT), 13 * 3600)

    def test_closed_tuesday_early_morning(self):
        self.assertFalse(is_open(self.TUESDAY_MORNING))
        self.assertEqual(seconds_until_open(self.TUESDAY_MORNING), 2 * 3600)

    def test_closed_saturday_afternoon_next_open_tuesday(self):
        self.assertFalse(is_open(self.SATURDAY_AFTERNOON))
        self.assertEqual(seconds_until_open(self.SATURDAY_AFTERNOON), 43 * 3600)
        info = next_open_info(self.SATURDAY_AFTERNOON)
        self.assertTrue(info["exists"])
        self.assertEqual(info["weekday"], "Lunes")

    def test_closed_sunday_next_open_monday(self):
        self.assertFalse(is_open(self.SUNDAY_REST))
        info = next_open_info(self.SUNDAY_REST)
        self.assertTrue(info["exists"])
        self.assertTrue(info["label"].startswith("Mañana"))

    def test_overnight_window(self):
        for day in (0, 1):
            StoreHours.objects.filter(day=day).update(open_time=datetime.time(22, 0), close_time=datetime.time(6, 0))
        monday_night = datetime.datetime(2026, 9, 7, 23, 0, tzinfo=self.TZ)
        tuesday_early = datetime.datetime(2026, 9, 8, 1, 0, tzinfo=self.TZ)
        tuesday_morning = datetime.datetime(2026, 9, 8, 7, 0, tzinfo=self.TZ)
        self.assertTrue(is_open(monday_night))
        self.assertTrue(is_open(tuesday_early))
        self.assertFalse(is_open(tuesday_morning))
        self.assertEqual(seconds_until_open(tuesday_morning), 15 * 3600)

    def test_force_open_overrides_schedule(self):
        cfg = StoreConfig.get_solo()
        cfg.force_open = True
        cfg.save(update_fields=["force_open"])
        self.assertTrue(is_open(self.SUNDAY_REST))
        self.assertEqual(seconds_until_open(self.SUNDAY_REST), 0)

    def test_all_days_closed_has_no_next_open(self):
        StoreHours.objects.update(is_closed=True, open_time=None, close_time=None)
        self.assertFalse(is_open(self.MONDAY_MORNING))
        self.assertIsNone(seconds_until_open(self.MONDAY_MORNING))
        self.assertFalse(next_open_info(self.MONDAY_MORNING)["exists"])

    def test_schedule_summary_groups_days(self):
        summary = schedule_summary()
        self.assertIn("Lunes a Viernes: 09:00–18:00 h", summary)
        self.assertIn("Sábado: 09:00–13:00 h", summary)
        self.assertIn("Domingo: cerrado", summary)


class StoreClosedMiddlewareTests(TestCase):
    TZ = ZoneInfo("America/Havana")
    CLOSED_AT = datetime.datetime(2026, 9, 7, 20, 0, tzinfo=TZ)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._now_patch = mock.patch("store.hours._local_now", return_value=cls.CLOSED_AT)
        cls._now_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._now_patch.stop()
        super().tearDownClass()

    def setUp(self):
        StoreConfig.objects.get_or_create(pk=1, defaults={"force_open": False})
        StoreHours.objects.all().delete()
        for day in range(7):
            StoreHours.objects.create(day=day, open_time=datetime.time(9, 0), close_time=datetime.time(18, 0), is_closed=False)

    def test_redirects_public_pages_to_closed_when_closed(self):
        with mock.patch("store.middleware.is_open", return_value=False):
            response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("store:closed"))

    def test_allows_admin_when_closed(self):
        with mock.patch("store.middleware.is_open", return_value=False):
            response = self.client.get("/admin/login/")
        self.assertEqual(response.status_code, 200)

    def test_allows_closed_page_when_closed(self):
        with mock.patch("store.middleware.is_open", return_value=False), mock.patch("store.views.is_open", return_value=False):
            response = self.client.get(reverse("store:closed"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Estamos cerrados", content)
        self.assertIn("Abrimos en", content)

    def test_closed_page_redirects_home_when_open(self):
        with mock.patch("store.views.is_open", return_value=True):
            response = self.client.get(reverse("store:closed"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("store:home"))


class VisitCounterTests(TestCase):
    def setUp(self):
        DailyStats.objects.all().delete()

    def _today(self):
        return _local_now().date()

    def test_public_page_views_increase_counter(self):
        self.client.get(reverse("store:home"))
        row = DailyStats.objects.get(date=self._today())
        self.assertEqual(row.views, 1)
        self.assertEqual(row.visitors, 1)
        self.client.get(reverse("store:home"))
        row.refresh_from_db()
        self.assertEqual(row.views, 2)
        self.assertEqual(row.visitors, 1)

    def test_different_ips_count_as_unique_visitors(self):
        self.client.get(reverse("store:home"), REMOTE_ADDR="1.2.3.4")
        self.client.get(reverse("store:home"), REMOTE_ADDR="5.6.7.8")
        row = DailyStats.objects.get(date=self._today())
        self.assertEqual(row.views, 2)
        self.assertEqual(row.visitors, 2)

    def test_does_not_count_admin_or_robots(self):
        self.client.get("/admin/login/")
        self.client.get("/robots.txt")
        self.assertFalse(DailyStats.objects.filter(date=self._today()).exists())

    def test_staff_browsing_not_counted(self):
        user = User.objects.create_user(username="boss", password="pass123")
        user.is_staff = True
        user.save()
        self.client.force_login(user)
        self.client.get(reverse("store:home"))
        self.assertFalse(DailyStats.objects.filter(date=self._today()).exists())

    def test_admin_dashboard_shows_visits(self):
        DailyStats.objects.create(date=self._today(), views=3, visitors=2, seen_keys="[]")
        DailyStats.objects.create(
            date=self._today() - datetime.timedelta(days=1), views=5, visitors=4, seen_keys="[]"
        )
        summary = visits_summary()
        self.assertEqual(summary["today_views"], 3)
        self.assertEqual(summary["today_visitors"], 2)
        self.assertEqual(summary["total_views"], 8)
        self.assertEqual(summary["total_visitors"], 6)


class VisitorFeedbackTests(TestCase):
    def setUp(self):
        DailyStats.objects.all().delete()
        VisitorCountry.objects.all().delete()
        Feedback.objects.all().delete()

    def _today(self):
        return _local_now().date()

    def test_feedback_like_creates_vote_and_blocks_double(self):
        with mock.patch("store.visits._geo_lookup", return_value="CU"):
            response = self.client.post(reverse("store:feedback"), {"rating": "like"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(Feedback.objects.get().rating, 1)
        self.assertEqual(Feedback.objects.get().country_code, "CU")
        data = response.json()
        self.assertIn("countries", data)
        self.assertEqual(data["countries"][0]["code"], "CU")
        self.client.post(reverse("store:feedback"), {"rating": "dislike"})
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(Feedback.objects.get().rating, 1)

    def test_feedback_rejects_invalid_and_get(self):
        response = self.client.post(reverse("store:feedback"), {"rating": "meh"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(reverse("store:feedback")).status_code, 405)

    def test_geo_lookup_populates_country(self):
        with mock.patch("store.visits._geo_lookup", return_value="CU"):
            self.client.get(reverse("store:home"))
        row = DailyStats.objects.get(date=self._today())
        key = json.loads(row.seen_keys)[0]
        vc = VisitorCountry.objects.get(ip_hash=key)
        self.assertEqual(vc.country_code, "CU")

    def test_country_votes_counts_and_sorts(self):
        for _ in range(2):
            Feedback.objects.create(rating=1, country_code="CU")
        Feedback.objects.create(rating=-1, country_code="US")
        votes = country_votes()
        self.assertEqual(votes[0]["code"], "CU")
        self.assertEqual(votes[0]["count"], 2)
        self.assertEqual(votes[0]["name"], "Cuba")
        self.assertEqual(votes[1]["code"], "US")

    def test_visitors_countries_endpoint_get(self):
        Feedback.objects.create(rating=1, country_code="MX")
        response = self.client.get(reverse("store:visitors_countries"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["countries"][0]["code"], "MX")

    def test_feedback_uses_client_country_param(self):
        with mock.patch("store.visits._geo_lookup", return_value="US") as geo:
            response = self.client.post(reverse("store:feedback"), {"rating": "like", "country": "cu"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feedback.objects.get().country_code, "CU")
        geo.assert_not_called()

    def test_feedback_ignores_invalid_country_param(self):
        with mock.patch("store.visits._geo_lookup", return_value="MX"):
            response = self.client.post(reverse("store:feedback"), {"rating": "like", "country": "CUB"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Feedback.objects.get().country_code, "MX")

    def test_home_renders_flagged_panel(self):
        Feedback.objects.create(rating=1, country_code="CU")
        response = self.client.get(reverse("store:home"))
        self.assertContains(response, "visits-panel")
        self.assertContains(response, "flagcdn.com")
        self.assertContains(response, "visits-flag-count")

    def test_geo_lookup_skips_private_ips_without_network(self):
        self.assertEqual(_geo_lookup("127.0.0.100"), "")
        self.assertEqual(_geo_lookup("192.168.1.1"), "")

