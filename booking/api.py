from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import APIException
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Booking, Master, Service
from .serializers import (
    AvailabilityQuerySerializer,
    BookingCreateSerializer,
    BookingSerializer,
    MasterSerializer,
    ReceiptSerializer,
    ServiceSerializer,
)
from .services import (
    DepositWindowClosed,
    InvalidTransition,
    SlotUnavailable,
    attach_receipt,
    create_booking,
)
from .slots import get_available_slots
from .tasks import send_receipt_for_review


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


class ServiceListView(generics.ListAPIView):
    queryset = Service.objects.filter(is_active=True)
    serializer_class = ServiceSerializer


class MasterListView(generics.ListAPIView):
    serializer_class = MasterSerializer

    def get_queryset(self):
        masters = Master.objects.filter(is_active=True).prefetch_related("services")
        service_id = self.request.query_params.get("service", "")
        if service_id.isdigit():
            masters = masters.filter(services=service_id)
        return masters


class AvailabilityView(APIView):
    def get(self, request):
        query = AvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        slots = get_available_slots(data["master"], data["service"], data["date"])
        return Response(
            {
                "date": data["date"],
                "slots": [timezone.localtime(slot).isoformat() for slot in slots],
            }
        )


class BookingCreateView(APIView):
    throttle_scope = "bookings"

    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = create_booking(**serializer.validated_data, source=Booking.Source.WEB)
        except SlotUnavailable:
            raise Conflict("This time is no longer available.", "slot_unavailable") from None
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class BookingDetailView(generics.RetrieveAPIView):
    queryset = Booking.objects.select_related("master", "service")
    serializer_class = BookingSerializer
    lookup_field = "code"


class ReceiptUploadView(APIView):
    throttle_scope = "receipts"
    parser_classes = [MultiPartParser]

    def post(self, request, code):
        booking = get_object_or_404(Booking, code=code)
        serializer = ReceiptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = attach_receipt(booking.pk, serializer.validated_data["receipt"])
        except DepositWindowClosed:
            raise Conflict("The deposit window has closed.", "deposit_window_closed") from None
        except InvalidTransition:
            raise Conflict("This booking does not expect a receipt.", "invalid_status") from None
        transaction.on_commit(lambda: send_receipt_for_review.delay(booking.pk))
        return Response(BookingSerializer(booking).data)
