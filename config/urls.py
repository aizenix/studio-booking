from django.contrib import admin
from django.urls import include, path

from booking import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("booking.urls")),
    path("receipts/<int:pk>/", views.receipt, name="booking-receipt"),
    path("healthz", views.healthz),
]
