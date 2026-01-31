from django.db import models
from django.contrib.auth.models import User
from datetime import date
from django.utils import timezone
from django.core.validators import MinValueValidator
from decimal import Decimal


# Пакет услуг
class Package(models.Model):
    name = models.CharField("Название пакета", max_length=150, unique=True)
    price = models.DecimalField(
        "Цена/мес.", 
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    is_promo = models.BooleanField("Акционный", default=False)
    promo_end_date = models.DateField("Дата окончания акции", blank=True, null=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Пакет"
        verbose_name_plural = "Пакеты"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.price}$)"

    @property
    def active_promo(self):
        """Возвращает True, если акция активна"""
        if self.is_promo and self.promo_end_date:
            return timezone.now().date() <= self.promo_end_date
        return self.is_promo


# Профиль менеджера
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField(
        "Телефон +992", 
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Формат: +992XXXXXXXXX"
    )
    balance = models.DecimalField(
        "Баланс менеджера", 
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    discount_percentage = models.DecimalField(
        "Индивидуальная скидка %",
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Автоматически рассчитывается по количеству клиентов"
    )
    manual_discount_percentage = models.DecimalField(
        "Ручная скидка % (бонус)",
        max_digits=5,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Дополнительная скидка, выданная вручную администратором. Суммируется с автоматической."
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Профиль менеджера"
        verbose_name_plural = "Профили менеджеров"

    def __str__(self):
        return f"Профиль {self.user.username}"
    
    def get_clients_count(self):
        """Возвращает количество АКТИВНЫХ клиентов, добавленных менеджером"""
        from datetime import date
        return self.user.clients.filter(end_date__gte=date.today()).count()
    
    def get_total_clients_count(self):
        """Возвращает общее количество всех клиентов (включая неактивных)"""
        return self.user.clients.count()
    
    def calculate_discount(self):
        """Автоматически рассчитывает скидку по количеству АКТИВНЫХ клиентов"""
        count = self.get_clients_count()
        
        if count >= 500:
            return Decimal('70.00')
        elif count >= 200:
            return Decimal('50.00')
        elif count >= 100:
            return Decimal('25.00')
        elif count >= 10:
            return Decimal('10.00')
        else:
            return Decimal('0.00')
    
    def update_discount(self):
        """Обновляет скидку и сохраняет в базу"""
        self.discount_percentage = self.calculate_discount()
        self.save(update_fields=['discount_percentage'])
        return self.discount_percentage
    
    def get_discounted_price(self, original_price):
        """Возвращает цену с учетом скидки"""
        if self.discount_percentage > 0:
            discount_amount = original_price * (self.discount_percentage / Decimal('100'))
            return original_price - discount_amount
        return original_price
    
    @property
    def next_discount_level(self):
        """Возвращает информацию о следующем уровне скидки"""
        count = self.get_clients_count()
        
        if count < 10:
            return {'clients_needed': 10 - count, 'discount': 10}
        elif count < 100:
            return {'clients_needed': 100 - count, 'discount': 25}
        elif count < 200:
            return {'clients_needed': 200 - count, 'discount': 50}
        elif count < 500:
            return {'clients_needed': 500 - count, 'discount': 70}
        else:
            return None  # Максимальная скидка достигнута
    
    def get_total_discount(self):
        """Возвращает итоговую скидку (автоматическая + ручная)"""
        total = self.discount_percentage + self.manual_discount_percentage
        # Максимум 99%
        return min(total, Decimal('99.00'))


# Клиент
class Client(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_EXPIRED = 'expired'
    STATUS_PENDING = 'pending'
    
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Активен'),
        (STATUS_EXPIRED, 'Истёк'),
        (STATUS_PENDING, 'Ожидание'),
    ]
    
    id = models.BigAutoField(primary_key=True)
    username = models.CharField("Логин", max_length=150, unique=True, db_index=True)
    password = models.CharField("Пароль", max_length=150)
    phone = models.CharField("Телефон", max_length=20, blank=True, null=True)

    subscription = models.CharField("Пакет / комментарий", max_length=255, blank=True, null=True)
    start_date = models.DateField("Дата начала", blank=True, null=True)
    end_date = models.DateField("Дата окончания", blank=True, null=True, db_index=True)
    info = models.TextField("Доп. информация", blank=True, null=True)

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="clients",
        null=True,
        blank=True,
        verbose_name="Добавлен менеджером"
    )

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        phone_display = self.phone if self.phone else 'без телефона'
        return f"{self.username} ({phone_display})"

    @property
    def remaining_days(self):
        """Возвращает количество оставшихся дней подписки"""
        if self.end_date:
            delta = (self.end_date - date.today()).days
            return max(0, delta)
        return None
    
    @property
    def status(self):
        """Возвращает текущий статус клиента"""
        if not self.end_date:
            return self.STATUS_PENDING
        remaining = self.remaining_days
        if remaining is None:
            return self.STATUS_PENDING
        return self.STATUS_ACTIVE if remaining > 0 else self.STATUS_EXPIRED
    
    @property
    def status_display(self):
        """Возвращает текстовое представление статуса"""
        status_dict = {
            self.STATUS_ACTIVE: 'Активен',
            self.STATUS_EXPIRED: 'Истёк',
            self.STATUS_PENDING: 'Ожидание',
        }
        return status_dict.get(self.status, 'Неизвестно')


class IPTVInfo(models.Model):
    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="iptv_info",
        verbose_name="Клиент",
    )
    standard_link = models.URLField("Стандартная ссылка", max_length=500, blank=True, null=True)
    short_link = models.URLField("Короткая ссылка", max_length=500, blank=True, null=True)
    m3u8_link = models.URLField("Скачать M3U8", max_length=500, blank=True, null=True)
    m3u_link = models.URLField("Скачать M3U", max_length=500, blank=True, null=True)
    spark_link = models.URLField("Скачать под Spark", max_length=500, blank=True, null=True)
    token = models.CharField("IPTV токен", max_length=128, blank=True, null=True)
    active_subscribers = models.PositiveIntegerField("Активные абоненты", blank=True, null=True)
    activated_per_day = models.PositiveIntegerField("Активировано за сутки", blank=True, null=True)
    activated_per_week = models.PositiveIntegerField("Активировано за неделю", blank=True, null=True)
    unused_funds = models.DecimalField("Непотраченные средства", max_digits=14, decimal_places=3, blank=True, null=True)
    total_channels = models.PositiveIntegerField("Количество каналов", default=1214)
    fetched_at = models.DateTimeField("Дата получения", auto_now_add=True)

    class Meta:
        verbose_name = "IPTV данные"
        verbose_name_plural = "IPTV данные"

    def __str__(self):
        return f"IPTV {self.client.username}"


# Настройки платежной карты (для админа)
class PaymentSettings(models.Model):
    card_number = models.CharField(
        "Номер карты",
        max_length=19,
        help_text="Формат: 0000 0000 0000 0000"
    )
    card_holder = models.CharField(
        "Владелец карты",
        max_length=100,
        blank=True,
        null=True
    )
    bank_name = models.CharField(
        "Название банка",
        max_length=100,
        blank=True,
        null=True
    )
    instructions = models.TextField(
        "Инструкции для пополнения",
        blank=True,
        null=True,
        help_text="Дополнительная информация для менеджеров"
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки оплаты"
        verbose_name_plural = "Настройки оплаты"

    def __str__(self):
        return f"Карта {self.card_number}"


# Заявки на пополнение баланса
class TopupRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Ожидает'),
        (STATUS_APPROVED, 'Одобрено'),
        (STATUS_REJECTED, 'Отклонено'),
    ]
    
    manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='topup_requests',
        verbose_name="Менеджер"
    )
    amount_tjs = models.DecimalField(
        "Сумма в TJS",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    amount_usd = models.DecimalField(
        "Сумма в USD",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    exchange_rate = models.DecimalField(
        "Курс обмена (TJS/USD)",
        max_digits=10,
        decimal_places=4,
        help_text="Курс на момент создания заявки"
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    transaction_proof = models.TextField(
        "Подтверждение перевода",
        blank=True,
        null=True,
        help_text="Номер транзакции, скриншот и т.д."
    )
    admin_comment = models.TextField(
        "Комментарий администратора",
        blank=True,
        null=True
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_topups',
        verbose_name="Одобрено"
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField("Обработано", null=True, blank=True)

    class Meta:
        verbose_name = "Заявка на пополнение"
        verbose_name_plural = "Заявки на пополнение"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['status', 'created_at']),
        ]

    def __str__(self):
        return f"{self.manager.username} - {self.amount_tjs} TJS ({self.amount_usd} USD) - {self.get_status_display()}"


# История транзакций
class Transaction(models.Model):
    manager = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Менеджер",
        related_name="transactions"
    )
    client = models.ForeignKey(
        "Client", 
        on_delete=models.CASCADE, 
        verbose_name="Клиент",
        related_name="transactions",
        null=True,
        blank=True
    )
    packages = models.TextField("Выбранные пакеты")
    total_cost = models.DecimalField(
        "Стоимость", 
        max_digits=10, 
        decimal_places=2
    )
    days_purchased = models.IntegerField("Куплено дней", default=0)
    comment = models.TextField("Комментарий", blank=True, null=True)
    created_at = models.DateTimeField("Дата операции", default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Транзакция"
        verbose_name_plural = "Транзакции"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['manager', 'created_at']),
        ]

    def __str__(self):
        manager_name = self.manager.username if self.manager else "Удалённый менеджер"
        if self.client:
            return f"{manager_name} -> {self.client.username} ({self.total_cost}$)"
        else:
            return f"Пополнение баланса: {manager_name} ({abs(self.total_cost)}$)"


# Объявления
class Announcement(models.Model):
    title = models.CharField(
        "Название",
        max_length=200,
        help_text="Заголовок объявления"
    )
    content = models.TextField(
        "Содержание",
        help_text="Текст объявления"
    )
    icon = models.CharField(
        "Иконка",
        max_length=50,
        default="📢",
        help_text="Используйте эмодзи или текст"
    )
    is_active = models.BooleanField(
        "Активно",
        default=True,
        help_text="Показывать ли это объявление на сайте"
    )
    order = models.IntegerField(
        "Порядок",
        default=0,
        help_text="Меньшее число = раньше в списке"
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.icon} {self.title}"


# Лог отправленных SMS
class SMSLog(models.Model):
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_PENDING = 'pending'
    
    STATUS_CHOICES = [
        (STATUS_SENT, 'Отправлено'),
        (STATUS_FAILED, 'Ошибка'),
        (STATUS_PENDING, 'Ожидание'),
    ]
    
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="sms_logs",
        verbose_name="Клиент"
    )
    phone = models.CharField("Номер телефона", max_length=20)
    message = models.TextField("Текст сообщения")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    response = models.TextField("Ответ API", blank=True, null=True)
    error = models.TextField("Ошибка", blank=True, null=True)
    sent_at = models.DateTimeField("Дата отправки", auto_now_add=True)
    
    class Meta:
        verbose_name = "SMS лог"
        verbose_name_plural = "SMS логи"
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['client', 'sent_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"SMS для {self.client.username} - {self.status} ({self.sent_at.strftime('%d.%m.%Y %H:%M')})"


# Прокси-модель для отображения системных логов в админке
class SystemLog(models.Model):
    class Meta:
        managed = False
        db_table = 'django_admin_log'
        verbose_name = "Системные логи"
        verbose_name_plural = "Системные логи"

    def __str__(self):
        return "System Logs"

# Информация о пакетах клиента со страницы дилера
class ClientPackageInfo(models.Model):
    client = models.OneToOneField(
        Client,
        on_delete=models.CASCADE,
        related_name="package_info",
        verbose_name="Клиент",
    )
    packages_html = models.TextField("HTML со списком пакетов", blank=True, null=True)
    packages_data = models.JSONField("Данные о пакетах", default=dict, blank=True)
    fetched_at = models.DateTimeField("Дата получения", auto_now=True)
    
    class Meta:
        verbose_name = "Информация о пакетах"
        verbose_name_plural = "Информация о пакетах"
        ordering = ['-fetched_at']
    
    def __str__(self):
        return f"Пакеты {self.client.username}"