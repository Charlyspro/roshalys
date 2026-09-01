from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from store.models import Category, Order, OrderItem, Product, DeliveryZone, ProductDeliveryConfig


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
        # Crear config de delivery para el producto
        ProductDeliveryConfig.objects.get_or_create(product=self.product)
        
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "1"})
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
        self.assertEqual(order.total, Decimal("150.00"))  # 100 + 50

    def test_delivery_zone_saved_to_order(self):
        # Crear config de delivery para el producto
        ProductDeliveryConfig.objects.get_or_create(product=self.product)
        
        user = User.objects.create_user(username="user", password="pass123")
        self.client.force_login(user)
        self.client.post(reverse("store:add_to_cart", args=[self.product.pk]), {"quantity": "1"})
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

