from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0026_client_dealer_sync_message_client_dealer_sync_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="package",
            name="port",
            field=models.CharField(blank=True, help_text="Например: 8080", max_length=50, null=True, verbose_name="Порт"),
        ),
    ]
