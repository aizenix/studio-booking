# studio-booking

[![CI](https://github.com/aizenix/studio-booking/actions/workflows/ci.yml/badge.svg)](https://github.com/aizenix/studio-booking/actions/workflows/ci.yml)

Booking backend for a tattoo studio: the website and a Telegram bot share one calendar, clients pay a deposit and send a photo of the receipt, unpaid bookings are released automatically after a timeout. A cleaned-up version of a project I built for a studio in Tashkent.

## Stack

Python 3.12, Django 5.2, Django REST Framework, aiogram 3, PostgreSQL 16, Redis, Celery + beat, Gunicorn, whitenoise. Tests run with pytest-django against a real Postgres, linting with ruff.

## Run with Docker

```bash
cp .env.example .env        # set TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID
docker compose up --build
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py seed_demo    # demo masters, services, hours
```

API is at http://localhost:8000/api/, admin at http://localhost:8000/admin/. Without a bot token the `bot` container exits, everything else keeps working.

## Run locally

Needs Postgres 16 and Redis, for example:

```bash
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
docker run -d -p 6379:6379 redis:7
```

Then:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver

# separate terminals
python manage.py runbot
celery -A config worker -l info
celery -A config beat -l info
```

## Tests

```bash
pytest
ruff check . && ruff format --check .
```

Tests need Postgres (connection settings come from the same `POSTGRES_*` variables). SQLite will not work because of the exclusion constraint.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/services/` | active services |
| GET | `/api/masters/?service=<id>` | masters, optionally filtered by service |
| GET | `/api/availability/?master=<id>&service=<id>&date=YYYY-MM-DD` | free start times |
| POST | `/api/bookings/` | create a booking, `409` if the time is taken |
| GET | `/api/bookings/<code>/` | booking status |
| POST | `/api/bookings/<code>/receipt/` | upload the receipt image (multipart, `receipt`) |
| GET | `/healthz` | liveness and DB check |

## Structure

```
config/     settings, urls, celery app
booking/    models, slot calculation, services, API, admin, celery tasks
bot/        aiogram routers, keyboards, message texts, runbot command
tests/
```

## Notes

- Double booking is stopped by the database, not by a Python check. `Booking` has an `ExclusionConstraint` on `(master, tstzrange(starts_at, ends_at))` for active statuses (needs `btree_gist`). Two clients can pass the availability check at the same moment, only one insert succeeds and the other gets `409`.
- Free slots come from one function, `booking.slots.get_available_slots`, which takes working hours, time off, active bookings, notice period and slot step into account. The API and the bot both call it, so the site and the bot never show different times.
- A booking holds its slot until `deposit_deadline` (30 minutes by default). A beat task expires overdue bookings every minute using `SELECT ... FOR UPDATE SKIP LOCKED`, so a receipt upload in progress is not expired under it.
- The bot reads through Django's async ORM. Writes go through the same service functions as the API, wrapped in `sync_to_async`, because the async ORM does not support transactions yet.
- Receipts are not served from a public media URL. Staff open them through a login-protected view linked from the admin.
