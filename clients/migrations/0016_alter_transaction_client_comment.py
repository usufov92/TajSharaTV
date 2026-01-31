# Generated migration for Transaction model changes
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0015_alter_client_options_alter_package_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='client',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='transactions',
                to='clients.client',
                verbose_name='Клиент'
            ),
        ),
        migrations.AddField(
            model_name='transaction',
            name='comment',
            field=models.TextField(blank=True, null=True, verbose_name='Комментарий'),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='total_cost',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Стоимость'),
        ),
    ]
