from django.conf import settings
from rest_framework import serializers

from .models import Booking, Master, Service
from .validators import normalize_phone

MAX_RECEIPT_SIZE = 5 * 1024 * 1024


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "description", "duration_minutes", "price", "deposit"]


class MasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Master
        fields = ["id", "name", "bio", "services"]


class MasterServiceSerializer(serializers.Serializer):
    master = serializers.PrimaryKeyRelatedField(queryset=Master.objects.filter(is_active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))

    def validate(self, attrs):
        if not attrs["master"].services.filter(pk=attrs["service"].pk).exists():
            raise serializers.ValidationError("This master does not do the selected service.")
        return attrs


class AvailabilityQuerySerializer(MasterServiceSerializer):
    date = serializers.DateField()


class BookingCreateSerializer(MasterServiceSerializer):
    starts_at = serializers.DateTimeField()
    client_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=32)

    def validate_phone(self, value):
        phone = normalize_phone(value)
        if phone is None:
            raise serializers.ValidationError("Enter a valid phone number.")
        return phone


class BookingSerializer(serializers.ModelSerializer):
    master = serializers.StringRelatedField()
    service = serializers.StringRelatedField()
    payment_details = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "code",
            "status",
            "master",
            "service",
            "starts_at",
            "ends_at",
            "deposit_amount",
            "deposit_deadline",
            "payment_details",
        ]

    def get_payment_details(self, booking):
        if booking.status != Booking.Status.PENDING_DEPOSIT:
            return None
        return settings.DEPOSIT_PAYMENT_DETAILS


class ReceiptSerializer(serializers.Serializer):
    receipt = serializers.ImageField()

    def validate_receipt(self, value):
        if value.size > MAX_RECEIPT_SIZE:
            raise serializers.ValidationError("The file is too large, 5 MB max.")
        return value
