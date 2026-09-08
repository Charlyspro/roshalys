from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path, re_path
from django.views.static import serve

from store.models import Category, Product


def robots_txt(request):
    domain = request.build_absolute_uri("/").rstrip("/")
    return render(request, "robots.txt", {"domain": domain}, content_type="text/plain")


def sitemap_xml(request):
    domain = request.build_absolute_uri("/").rstrip("/")
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.filter(is_active=True)
    return render(
        request,
        "sitemap.xml",
        {
            "domain": domain,
            "products": products,
            "categories": categories,
            "pages": ["", "buscar/", "cart/"],
        },
        content_type="application/xml",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("store.urls", "store"), namespace="store")),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    if settings.MEDIA_URL.startswith("/"):
        media_url_path = settings.MEDIA_URL.lstrip("/")
        urlpatterns += [re_path(rf"^{media_url_path}(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
