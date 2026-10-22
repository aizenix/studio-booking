from datetime import time

from django.core.management.base import BaseCommand
from django.db import transaction

from booking.models import Master, Service, WorkingHours

SERVICES = [
    # name, minutes, price, deposit (UZS)
    ("Small tattoo", 60, 400_000, 100_000),
    ("Medium tattoo", 180, 1_200_000, 300_000),
    ("Full day session", 360, 2_500_000, 500_000),
    ("Piercing", 30, 150_000, 50_000),
]

MASTERS = {
    "Aziza": ["Small tattoo", "Medium tattoo", "Full day session"],
    "Timur": ["Small tattoo", "Medium tattoo"],
    "Malika": ["Piercing", "Small tattoo"],
}


class Command(BaseCommand):
    help = "Create demo masters, services and working hours."

    @transaction.atomic
    def handle(self, *args, **options):
        services = {}
        for name, minutes, price, deposit in SERVICES:
            services[name], _ = Service.objects.get_or_create(
                name=name,
                defaults={"duration_minutes": minutes, "price": price, "deposit": deposit},
            )

        for name, service_names in MASTERS.items():
            master, _ = Master.objects.get_or_create(name=name)
            master.services.set([services[service_name] for service_name in service_names])
            for weekday in range(6):
                WorkingHours.objects.update_or_create(
                    master=master,
                    weekday=weekday,
                    defaults={"start_time": time(11), "end_time": time(20)},
                )

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
