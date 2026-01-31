from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0018_announcement"),
    ]

    operations = [
        migrations.AddField(
            model_name="iptvinfo",
            name="token",
            field=models.CharField(blank=True, max_length=128, null=True, verbose_name="IPTV токен"),
        ),
        migrations.AddField(
            model_name="iptvinfo",
            name="active_subscribers",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Активные абоненты"),
        ),
        migrations.AddField(
            model_name="iptvinfo",
            name="activated_per_day",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Активировано за сутки"),
        ),
        migrations.AddField(
            model_name="iptvinfo",
            name="activated_per_week",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Активировано за неделю"),
        ),
        migrations.AddField(
            model_name="iptvinfo",
            name="unused_funds",
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=14, null=True, verbose_name="Непотраченные средства"),
        ),
    ]
