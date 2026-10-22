from django.contrib.admin.views.decorators import staff_member_required
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404

from .models import Booking


def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "db": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@staff_member_required
def receipt(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not booking.receipt:
        raise Http404
    return FileResponse(booking.receipt.open("rb"))
