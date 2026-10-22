import booking.models
import django.contrib.postgres.constraints
import django.contrib.postgres.operations
import django.contrib.postgres.fields.ranges
import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        django.contrib.postgres.operations.BtreeGistExtension(),
        migrations.CreateModel(
            name='Service',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True)),
                ('duration_minutes', models.PositiveSmallIntegerField()),
                ('price', models.PositiveIntegerField()),
                ('deposit', models.PositiveIntegerField()),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Master',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('bio', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('services', models.ManyToManyField(blank=True, related_name='masters', to='booking.service')),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Booking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('client_name', models.CharField(max_length=100)),
                ('phone', models.CharField(max_length=20)),
                ('telegram_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('source', models.CharField(choices=[('web', 'Website'), ('bot', 'Telegram bot')], max_length=10)),
                ('status', models.CharField(choices=[('pending_deposit', 'Pending deposit'), ('awaiting_confirmation', 'Awaiting confirmation'), ('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('expired', 'Expired')], db_index=True, default='pending_deposit', max_length=30)),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
                ('deposit_amount', models.PositiveIntegerField()),
                ('deposit_deadline', models.DateTimeField(blank=True, null=True)),
                ('receipt', models.ImageField(blank=True, upload_to=booking.models.receipt_upload_to)),
                ('reminded_24h', models.BooleanField(default=False)),
                ('reminded_2h', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('master', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='booking.master')),
                ('service', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='bookings', to='booking.service')),
            ],
            options={
                'ordering': ['-starts_at'],
                'indexes': [models.Index(fields=['status', 'deposit_deadline'], name='booking_boo_status_0f1f79_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(('ends_at__gt', models.F('starts_at'))), name='booking_end_after_start'), django.contrib.postgres.constraints.ExclusionConstraint(condition=models.Q(('status__in', ['pending_deposit', 'awaiting_confirmation', 'confirmed'])), expressions=[(booking.models.TsTzRange('starts_at', 'ends_at', django.contrib.postgres.fields.ranges.RangeBoundary()), '&&'), ('master', '=')], name='booking_no_overlap')],
            },
        ),
        migrations.CreateModel(
            name='TimeOff',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
                ('reason', models.CharField(blank=True, max_length=200)),
                ('master', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='time_off', to='booking.master')),
            ],
            options={
                'verbose_name_plural': 'time off',
                'ordering': ['-starts_at'],
                'constraints': [models.CheckConstraint(condition=models.Q(('ends_at__gt', models.F('starts_at'))), name='time_off_end_after_start')],
            },
        ),
        migrations.CreateModel(
            name='WorkingHours',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('weekday', models.PositiveSmallIntegerField(choices=[(0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday')])),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('master', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='working_hours', to='booking.master')),
            ],
            options={
                'verbose_name_plural': 'working hours',
                'ordering': ['master', 'weekday'],
                'constraints': [models.UniqueConstraint(fields=('master', 'weekday'), name='one_schedule_per_weekday'), models.CheckConstraint(condition=models.Q(('end_time__gt', models.F('start_time'))), name='working_hours_end_after_start')],
            },
        ),
    ]
