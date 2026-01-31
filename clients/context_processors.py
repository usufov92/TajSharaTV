"""Контекстные процессоры для глобальных переменных шаблонов"""

from django.conf import settings
from .models import Announcement


def announcements(request):
    """Добавляет активные объявления в контекст всех шаблонов"""
    announcements_list = Announcement.objects.filter(is_active=True).order_by('order')
    return {
        'announcements': announcements_list,
    }


def links(request):
    """Глобальные ссылки (например, второй инстанс IPTV)"""
    return {
        'iptv_url': getattr(settings, 'IPTV_URL', None),
        'tajsharatv_url': getattr(settings, 'TAJSHARATV_URL', None),
        'site_brand': getattr(settings, 'SITE_BRAND', 'TajSharaTV'),
        'peer_brand': getattr(settings, 'PEER_BRAND', 'Taj-IPTV'),
        'peer_url': getattr(settings, 'PEER_URL', getattr(settings, 'IPTV_URL', None)),
    }
