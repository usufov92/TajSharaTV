"""
Management command для автоматической отправки SMS и Telegram уведомлений клиентам
об истечении срока подписки (за 1 день до окончания).
Запускается 3 раза в день через Task Scheduler.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from clients.models import Client, SMSLog
from clients.sms_service import get_sms_service
from clients.telegram_notify import notify_expiry_warning
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправка SMS-уведомлений клиентам за 3 дня до окончания подписки'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Тестовый режим (не отправлять SMS, только показать список клиентов)',
        )
        parser.add_argument(
            '--force-phone',
            type=str,
            help='Отправить тестовое SMS на указанный номер',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force_phone = options.get('force_phone')
        
        # Тестовая отправка на конкретный номер
        if force_phone:
            self.stdout.write(self.style.WARNING(f"Тестовая отправка на {force_phone}"))
            result = self._send_test_sms(force_phone)
            sms_result = result.get('sms', {})
            wa_result = result.get('whatsapp', {})
            if sms_result.get('success') or wa_result.get('success'):
                self.stdout.write(self.style.SUCCESS(f"✅ Уведомление отправлено (SMS: {sms_result.get('success')}, WhatsApp: {wa_result.get('success')})"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Ошибка отправки: {result}"))
            return
        
        # Вычисляем дату: 1 день спустя (т.е. за 1 день до истечения)
        expiry_date = date.today() + timedelta(days=1)
        
        self.stdout.write(self.style.NOTICE(f"\n📅 Проверка клиентов с окончанием подписки: {expiry_date.strftime('%d.%m.%Y')}"))
        
        # Получаем клиентов, у которых подписка истекает завтра
        expiring_clients = Client.objects.filter(
            end_date=expiry_date,
            phone__isnull=False
        ).exclude(phone='')
        
        total = expiring_clients.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING("Клиентов с истекающими подписками не найдено."))
            return
        
        self.stdout.write(self.style.SUCCESS(f"Найдено клиентов: {total}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 ТЕСТОВЫЙ РЕЖИМ (SMS не отправляются)\n"))
            for client in expiring_clients:
                self.stdout.write(f"  📱 {client.username} → {client.phone}")
            return
        
        # Отправка SMS и Telegram
        sms_service = get_sms_service()
        sent_count = 0
        failed_count = 0
        telegram_sent = 0
        
        self.stdout.write(self.style.NOTICE("\n📨 Начинаем отправку уведомлений...\n"))
        
        for client in expiring_clients:
            # Проверка: не отправляли ли уже сегодня
            today_logs = SMSLog.objects.filter(
                client=client,
                sent_at__date=date.today(),
                status=SMSLog.STATUS_SENT
            )
            
            if today_logs.exists():
                self.stdout.write(
                    self.style.WARNING(f"  ⏭️  {client.username} - SMS уже отправлено сегодня")
                )
                continue
            
            # Телефон менеджера (если есть профиль)
            manager_phone = None
            if client.created_by and hasattr(client.created_by, 'profile'):
                manager_phone = client.created_by.profile.phone

            # Отправка SMS
            result = sms_service.send_expiry_notification(
                phone=client.phone,
                client_name=client.username,
                manager_phone=manager_phone
            )
            
            # Логирование результата
            sms_log = SMSLog.objects.create(
                client=client,
                phone=result.get('phone', client.phone),
                message=result.get('sent_message', "Напоминаем: завтра истекает срок оплаты IPTV."),
                status=SMSLog.STATUS_SENT if result['success'] else SMSLog.STATUS_FAILED,
                response=str(result.get('response', '')),
                error=result.get('error', '')
            )
            
            if result['success']:
                sent_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✅ SMS {client.username} ({client.phone}) - отправлено")
                )
            else:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  ❌ SMS {client.username} ({client.phone}) - ошибка: {result['message']}"
                    )
                )
            
            # 📱 Отправка Telegram уведомления менеджеру
            if client.created_by:
                try:
                    tg_result = notify_expiry_warning(
                        username=client.username,
                        subscription=client.subscription or "IPTV",
                    )
                    if tg_result:
                        telegram_sent += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"  📱 Telegram {client.username} - отправлено")
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f"  ⚠️  Telegram {client.username} - ошибка: {e}")
                    )
        
        # Итоговая статистика
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS(f"✅ SMS отправлено: {sent_count}"))
        self.stdout.write(self.style.SUCCESS(f"📱 Telegram отправлено: {telegram_sent}"))
        if failed_count > 0:
            self.stdout.write(self.style.ERROR(f"❌ SMS ошибок: {failed_count}"))
        self.stdout.write(self.style.NOTICE(f"📊 Всего обработано: {total}"))
        self.stdout.write("="*60 + "\n")
        
        logger.info(f"Уведомления: SMS {sent_count}, Telegram {telegram_sent}, ошибок {failed_count}")
    
    def _send_test_sms(self, phone: str) -> dict:
                # --- Новый универсальный блок уведомлений ---
                from clients.sms_service import send_notification
                result = send_notification(
                    phone=client.phone,
                    username=client.username,
                    manager=manager_phone
                )
                # Логирование SMS
                sms_result = result.get('sms', {})
                SMSLog.objects.create(
                    client=client,
                    phone=client.phone,
                    message=message,
                    status=SMSLog.STATUS_SENT if sms_result.get('success') else SMSLog.STATUS_FAILED,
                    response=str(sms_result.get('response', '')),
                    error=sms_result.get('error', '')
                )
                # Логирование WhatsApp (можно добавить отдельную модель для логов WhatsApp при необходимости)
                wa_result = result.get('whatsapp', {})
                if sms_result.get('success') or wa_result.get('success'):
                    sent_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  ✅ {client.username} ({client.phone}) - уведомление отправлено (SMS: {sms_result.get('success')}, WhatsApp: {wa_result.get('success')})")
                    )
                else:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ❌ {client.username} ({client.phone}) - ошибка: {result}" 
                        )
                    )
    def _send_test_sms(self, phone: str) -> dict:
        """Отправка тестового уведомления через SMS и WhatsApp"""
        from clients.sms_service import send_notification
        return send_notification(phone=phone, username='Тестовый', manager=None)
