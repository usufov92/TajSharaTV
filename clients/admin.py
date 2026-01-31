from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncMonth
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from django.conf import settings
from pathlib import Path
from datetime import datetime
import os
from .models import Client, Profile, Package, Transaction, TopupRequest, PaymentSettings, Announcement, SMSLog, SystemLog


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "balance", "discount_info", "clients_count", "created_at")
    search_fields = ("user__username", "phone")
    list_editable = ("balance",)
    list_filter = ("created_at",)
    readonly_fields = ("discount_percentage", "created_at", "updated_at", "clients_count_detail", "total_discount_display")
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'phone', 'balance')
        }),
        ('Скидки и комиссии', {
            'fields': ('discount_percentage', 'manual_discount_percentage', 'total_discount_display'),
            'description': 'Автоматическая скидка вычисляется по активным клиентам. Ручная скидка добавляется вручную администратором.'
        }),
        ('Статистика и скидки', {
            'fields': ('clients_count_detail',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def discount_info(self, obj):
        """Показывает итоговую скидку в списке"""
        auto_discount = obj.discount_percentage
        manual_discount = obj.manual_discount_percentage
        total_discount = obj.get_total_discount()
        
        if manual_discount > 0:
            return format_html(
                '<span style="color: #2ed573; font-weight: bold;">{}</span>% '
                '<span style="font-size: 11px; color: #999;">({}% + {}%)</span>',
                total_discount, auto_discount, manual_discount
            )
        else:
            return format_html('<span style="color: #5bc0be;">{}</span>%', auto_discount)
    discount_info.short_description = "Итоговая скидка"
    
    def total_discount_display(self, obj):
        """Красивое отображение итоговой скидки"""
        auto_discount = obj.discount_percentage
        manual_discount = obj.manual_discount_percentage
        total_discount = obj.get_total_discount()
        
        html = f'<div style="padding: 15px; background: linear-gradient(135deg, rgba(46, 213, 115, 0.1) 0%, rgba(91, 192, 190, 0.1) 100%); border-radius: 8px; border-left: 4px solid #2ed573;">'
        html += f'<p style="margin: 5px 0;"><strong>Автоматическая скидка:</strong> <span style="color: #5bc0be; font-size: 18px; font-weight: bold;">{auto_discount}%</span></p>'
        html += f'<p style="margin: 5px 0;"><strong>Ручная скидка (бонус):</strong> <span style="color: #ffb800; font-size: 18px; font-weight: bold;">{manual_discount}%</span></p>'
        html += f'<hr style="border: none; border-top: 1px solid rgba(91, 192, 190, 0.3); margin: 10px 0;">'
        html += f'<p style="margin: 5px 0;"><strong>ИТОГОВАЯ СКИДКА:</strong> <span style="color: #2ed573; font-size: 24px; font-weight: bold;">{total_discount}%</span></p>'
        html += '</div>'
        return format_html(html)
    total_discount_display.short_description = "Итоговая скидка (автоматическая + ручная)"
    
    def clients_count(self, obj):
        count = Client.objects.filter(created_by=obj.user).count()
        active_count = obj.get_clients_count()
        if active_count >= 500:
            color = '#2ed573'
        elif active_count >= 200:
            color = '#ffa502'
        elif active_count >= 100:
            color = '#ff6b6b'
        elif active_count >= 10:
            color = '#5bc0be'
        else:
            color = '#666'
        return format_html('<b style="color: {};">{}</b> <span style="color: #999;">/ {}</span>', color, active_count, count)
    clients_count.short_description = "Активных / Всего"
    
    def clients_count_detail(self, obj):
        count = obj.get_clients_count()
        total_count = obj.get_total_clients_count()
        discount = obj.discount_percentage
        next_level = obj.next_discount_level
        
        html = f'<div style="padding: 10px; background: #f5f5f5; border-radius: 5px;">'
        html += f'<p><strong>Активных клиентов:</strong> <span style="color: #2ed573; font-size: 18px; font-weight: bold;">{count}</span></p>'
        html += f'<p><strong>Всего клиентов:</strong> {total_count}</p>'
        html += f'<p><strong>Текущая скидка:</strong> <span style="color: #2ed573; font-size: 18px; font-weight: bold;">{discount}%</span></p>'
        
        if next_level:
            html += f'<p><strong>До следующего уровня:</strong> +{next_level["clients_needed"]} активных клиентов → {next_level["discount"]}%</p>'
        else:
            html += f'<p style="color: #2ed573;"><strong>🎉 Максимальная скидка достигнута!</strong></p>'
        
        html += '</div>'
        return format_html(html)
    clients_count_detail.short_description = "Детали по клиентам и скидкам"
    
    actions = ['update_all_discounts', 'set_manual_discount']
    
    def update_all_discounts(self, request, queryset):
        updated = 0
        for profile in queryset:
            old_discount = profile.discount_percentage
            new_discount = profile.update_discount()
            if old_discount != new_discount:
                updated += 1
        
        self.message_user(
            request,
            f"Обновлено скидок: {updated} из {queryset.count()}"
        )
    update_all_discounts.short_description = "🔄 Обновить автоматические скидки для выбранных"
    
    def set_manual_discount(self, request, queryset):
        """Экшн для выдачи ручной скидки"""
        from django.shortcuts import redirect
        return redirect('admin:set_manager_discount')
    set_manual_discount.short_description = "🎁 Выдать ручную скидку"


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("username", "phone", "subscription", "start_date", "end_date", "created_by", "created_at")
    search_fields = ("username", "phone", "subscription", "info")
    list_filter = ("created_by", "created_at", "end_date")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "price", "is_promo", "promo_end_date", "active_promo", "created_at")
    list_editable = ("price", "is_promo", "promo_end_date")
    search_fields = ("name",)
    list_filter = ("is_promo", "created_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "manager", "client", "transaction_type", "total_cost", "days_purchased", "comment_short", "created_at")
    search_fields = ("manager__username", "client__username", "packages", "comment")
    list_filter = ("manager", "created_at")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
    
    def transaction_type(self, obj):
        """Показывает тип транзакции"""
        if obj.client is None and obj.total_cost < 0:
            return format_html('<span style="color: green; font-weight: bold;">{}</span>', '💰 Пополнение')
        elif obj.client:
            return format_html('<span style="color: blue;">{}</span>', '💳 Покупка пакета')
        return "Неизвестно"
    transaction_type.short_description = "Тип"
    
    def comment_short(self, obj):
        """Показывает краткий комментарий"""
        if obj.comment:
            return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
        return "-"
    comment_short.short_description = "Комментарий"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("analytics/", self.admin_site.admin_view(self.analytics_view), name="transaction-analytics"),
        ]
        return custom_urls + urls

    def analytics_view(self, request):
        total_sum = Transaction.objects.aggregate(Sum("total_cost"))["total_cost__sum"] or 0
        total_transactions = Transaction.objects.count()

        top_managers = (
            Transaction.objects.values("manager__username")
            .annotate(total=Sum("total_cost"), count=Count("id"))
            .order_by("-total")[:5]
        )

        top_clients = (
            Transaction.objects.values("client__username")
            .annotate(total=Sum("total_cost"), count=Count("id"))
            .order_by("-count")[:5]
        )

        daily_stats = (
            Transaction.objects.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"), total=Sum("total_cost"))
            .order_by("day")
        )

        monthly_stats = (
            Transaction.objects.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"), total=Sum("total_cost"))
            .order_by("month")
        )

        context = dict(
            self.admin_site.each_context(request),
            total_sum=total_sum,
            total_transactions=total_transactions,
            top_managers=top_managers,
            top_clients=top_clients,
            daily_stats=list(daily_stats),
            monthly_stats=list(monthly_stats),
        )
        return TemplateResponse(request, "transaction_analytics.html", context)


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    list_display = ("card_number", "card_holder", "bank_name", "updated_at")
    readonly_fields = ("updated_at",)



@admin.register(TopupRequest)
class TopupRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "manager", "amount_tjs", "amount_usd", "exchange_rate", "status_badge", "created_at", "processed_at")
    list_filter = ("status", "created_at", "processed_at")
    search_fields = ("manager__username", "transaction_proof", "admin_comment")
    readonly_fields = ("manager", "amount_tjs", "amount_usd", "exchange_rate", "created_at", "transaction_proof")
    date_hierarchy = "created_at"
    actions = ["approve_requests", "reject_requests"]
    
    fieldsets = (
        ("Информация о заявке", {
            "fields": ("manager", "amount_tjs", "amount_usd", "exchange_rate", "status", "created_at")
        }),
        ("Подтверждение перевода", {
            "fields": ("transaction_proof",)
        }),
        ("Обработка администратором", {
            "fields": ("admin_comment", "approved_by", "processed_at")
        }),
    )
    
    def status_badge(self, obj):
        """Показывает статус с цветным бейджем"""
        colors = {
            'pending': 'orange',
            'approved': 'green',
            'rejected': 'red',
        }
        icons = {
            'pending': '⏳',
            'approved': '✅',
            'rejected': '❌',
        }
        color = colors.get(obj.status, 'gray')
        icon = icons.get(obj.status, '❓')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = "Статус"
    
    def approve_requests(self, request, queryset):
        """Одобрить выбранные заявки"""
        approved_count = 0
        for topup in queryset.filter(status='pending'):
            # Добавляем баланс менеджеру
            profile, _ = Profile.objects.get_or_create(user=topup.manager)
            profile.balance += topup.amount_usd
            profile.save()
            
            # Создаём транзакцию
            Transaction.objects.create(
                manager=topup.manager,
                client=None,
                packages=f"Пополнение баланса (Заявка #{topup.id})",
                total_cost=-topup.amount_usd,
                days_purchased=0,
                comment=f"Пополнение на {topup.amount_tjs} TJS (курс {topup.exchange_rate})"
            )
            
            # Обновляем статус заявки
            topup.status = 'approved'
            topup.approved_by = request.user
            topup.processed_at = timezone.now()
            topup.save()
            approved_count += 1
        
        self.message_user(request, f"Одобрено заявок: {approved_count}")
    approve_requests.short_description = "✅ Одобрить выбранные заявки"
    
    def reject_requests(self, request, queryset):
        """Отклонить выбранные заявки"""
        rejected_count = queryset.filter(status='pending').update(
            status='rejected',
            approved_by=request.user,
            processed_at=timezone.now()
        )
        self.message_user(request, f"Отклонено заявок: {rejected_count}")
    reject_requests.short_description = "❌ Отклонить выбранные заявки"


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("icon_title", "is_active", "order", "created_at", "updated_at")
    list_editable = ("is_active", "order")
    list_filter = ("is_active", "created_at")
    search_fields = ("title", "content")
    readonly_fields = ("created_at", "updated_at")
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("title", "content", "icon")
        }),
        ("Настройки", {
            "fields": ("is_active", "order")
        }),
        ("Даты", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    def icon_title(self, obj):
        """Показывает иконку и название"""
        return format_html(
            '<span style="font-size: 20px; margin-right: 10px;">{}</span>{}',
            obj.icon, obj.title
        )
    icon_title.short_description = "Объявление"
    
    def is_active_badge(self, obj):
        """Показывает статус с бейджем"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">{}</span>', '✅ Активно'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">{}</span>', '❌ Неактивно'
        )
    is_active_badge.short_description = "Статус"


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("client_link", "phone", "status_badge", "sent_at", "message_preview")
    search_fields = ("client__username", "phone", "message")
    list_filter = ("status", "sent_at")
    readonly_fields = ("client", "phone", "message", "status", "response", "error", "sent_at")
    date_hierarchy = "sent_at"
    
    def has_add_permission(self, request):
        """Запретить ручное создание логов"""
        return False
    
    def client_link(self, obj):
        """Ссылка на клиента"""
        return format_html(
            '<a href="/admin/clients/client/{}/change/">{}</a>',
            obj.client.id, obj.client.username
        )
    client_link.short_description = "Клиент"
    
    def status_badge(self, obj):
        """Цветной статус"""
        colors = {
            'sent': 'green',
            'failed': 'red',
            'pending': 'orange'
        }
        icons = {
            'sent': '✅',
            'failed': '❌',
            'pending': '⏳'
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            colors.get(obj.status, 'gray'),
            icons.get(obj.status, ''),
            obj.get_status_display()
        )
    status_badge.short_description = "Статус"
    
    def message_preview(self, obj):
        """Превью сообщения"""
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = "Текст SMS"


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag", "change_message")
    list_filter = ("user", "content_type", "action_flag", "action_time")
    search_fields = ("object_repr", "change_message")
    date_hierarchy = "action_time"
    readonly_fields = ("action_time", "user", "content_type", "object_id", "object_repr", "action_flag", "change_message")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    change_list_template = "admin/system_logs.html"
    list_display = ("__str__",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        def tail(file_path, lines=400):
            if not os.path.exists(file_path):
                return []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = f.readlines()
            return data[-lines:]

        base_dir = Path(settings.BASE_DIR)
        log_candidates = list(base_dir.glob("*.log*"))
        log_candidates += list((base_dir / "logs").glob("*.log*"))

        # Убираем дубликаты по абсолютному пути и сортируем по имени
        unique_paths = {}
        for p in log_candidates:
            unique_paths[str(p.resolve())] = p

        logs_context = []
        for p in sorted(unique_paths.values(), key=lambda x: x.name.lower()):
            path_str = str(p)
            exists = p.exists()
            stat = p.stat() if exists else None
            logs_context.append({
                "name": p.name,
                "path": path_str,
                "exists": exists,
                "size": stat.st_size if stat else 0,
                "mtime": datetime.fromtimestamp(stat.st_mtime) if stat else None,
                "content": tail(path_str),
            })

        extra_context = extra_context or {}
        extra_context.update({
            "title": "Системные логи",
            "logs": logs_context,
        })
        return super().changelist_view(request, extra_context=extra_context)
