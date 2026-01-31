from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0018_announcement'),
    ]

    operations = [
        migrations.CreateModel(
            name='IPTVInfo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('standard_link', models.URLField(blank=True, max_length=500, null=True, verbose_name='Стандартная ссылка')),
                ('short_link', models.URLField(blank=True, max_length=500, null=True, verbose_name='Короткая ссылка')),
                ('m3u8_link', models.URLField(blank=True, max_length=500, null=True, verbose_name='Скачать M3U8')),
                ('m3u_link', models.URLField(blank=True, max_length=500, null=True, verbose_name='Скачать M3U')),
                ('spark_link', models.URLField(blank=True, max_length=500, null=True, verbose_name='Скачать под Spark')),
                ('total_channels', models.PositiveIntegerField(default=1214, verbose_name='Количество каналов')),
                ('fetched_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата получения')),
                ('client', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='iptv_info', to='clients.client', verbose_name='Клиент')),
            ],
            options={
                'verbose_name': 'IPTV данные',
                'verbose_name_plural': 'IPTV данные',
            },
        ),
    ]
