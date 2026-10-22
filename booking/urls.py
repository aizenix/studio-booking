from django.urls import path

from . import api

urlpatterns = [
    path("services/", api.ServiceListView.as_view()),
    path("masters/", api.MasterListView.as_view()),
    path("availability/", api.AvailabilityView.as_view()),
    path("bookings/", api.BookingCreateView.as_view()),
    path("bookings/<uuid:code>/", api.BookingDetailView.as_view()),
    path("bookings/<uuid:code>/receipt/", api.ReceiptUploadView.as_view()),
]
