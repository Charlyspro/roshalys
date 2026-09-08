from django.shortcuts import redirect
from django.urls import reverse

from store.hours import is_open
from store.visits import record_visit

CLOSED_ALLOW_EXACT = ("/robots.txt", "/sitemap.xml")
CLOSED_ALLOW_PREFIXES = ("/admin/", "/static/", "/media/", "/cerrado/")


class StoreClosedMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not is_open() and not self._allowed(request.path):
            return redirect(reverse("store:closed"))
        return self.get_response(request)

    @staticmethod
    def _allowed(path):
        if path in CLOSED_ALLOW_EXACT:
            return True
        return any(path.startswith(prefix) for prefix in CLOSED_ALLOW_PREFIXES)


class VisitCounterMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 200 and not getattr(request.user, "is_staff", False):
            record_visit(request)
        return response