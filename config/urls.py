from django.contrib import admin
from django.urls import include, path

from booking.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("booking.urls")),
    path("healthz", healthz),
]
