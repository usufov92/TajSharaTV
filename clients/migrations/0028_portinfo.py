from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0027_package_port"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortInfo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_name", models.CharField(max_length=200, verbose_name="Название пакета")),
                ("provider", models.CharField(blank=True, max_length=200, null=True, verbose_name="Провайдер")),
                ("caid_provid", models.CharField(blank=True, help_text="Например: 0500:050F00", max_length=100, null=True, verbose_name="CAID:ProvID")),
                ("camd", models.CharField(blank=True, max_length=100, null=True, verbose_name="camd")),
                ("cccam", models.CharField(blank=True, max_length=100, null=True, verbose_name="cccam")),
                ("newcamd", models.CharField(blank=True, max_length=100, null=True, verbose_name="newcamd")),
                ("mgcamd", models.CharField(blank=True, max_length=100, null=True, verbose_name="mgcamd")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
            ],
            options={
                "verbose_name": "Информация о портах",
                "verbose_name_plural": "Таблица портов",
                "ordering": ["package_name"],
            },
        ),
    ]
