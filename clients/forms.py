from django import forms
from django.core.validators import RegexValidator
from decimal import Decimal
from .models import Client, Profile


# ➕ Форма добавления клиента
class ClientForm(forms.ModelForm):
    """Форма для добавления и редактирования клиента"""
    
    # Валидатор для логина - только латинские маленькие буквы и цифры
    username_validator = RegexValidator(
        regex=r'^[a-z0-9]+$',
        message="Логин может содержать только латинские маленькие буквы (a-z) и цифры (0-9)"
    )
    
    # Валидатор для телефона
    phone_validator = RegexValidator(
        regex=r'^\+?992\d{9}$',
        message="Введите номер в формате: +992XXXXXXXXX"
    )
    
    username = forms.CharField(
        required=True,
        validators=[username_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: client123',
            'pattern': r'^[a-z0-9]+$'
        }),
        help_text="Только латинские маленькие буквы и цифры"
    )
    
    phone = forms.CharField(
        required=False,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: +992XXXXXXXXX',
            'pattern': r'\+?992\d{9}'
        }),
        help_text="Формат: +992XXXXXXXXX"
    )
    
    class Meta:
        model = Client
        fields = ['username', 'password', 'phone', 'subscription']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: client123',
                'pattern': r'^[a-z0-9]+$',
                'required': True
            }),
            'password': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: SecurePass123',
                'required': True
            }),
            'subscription': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Примечание к клиенту',
                'rows': 3
            }),
        }
        labels = {
            'username': '👤 Логин клиента',
            'password': '🔑 Пароль',
            'phone': '📞 Телефон',
            'subscription': '📝 Примечание',
        }
        help_texts = {
            'username': 'Уникальный логин для клиента',
            'password': 'Пароль для доступа в систему',
            'subscription': 'Дополнительная информация о клиенте'
        }
    
    def clean_username(self):
        """Валидация логина"""
        username = self.cleaned_data.get('username')
        if username:
            username = username.strip()
            if len(username) < 4:
                raise forms.ValidationError("Логин должен содержать минимум 4 символа")
            # Проверка на уникальность (только для новых клиентов)
            if not self.instance.pk:
                if Client.objects.filter(username=username).exists():
                    raise forms.ValidationError(f"Клиент с логином '{username}' уже существует")
        return username
    
    def clean_password(self):
        """Валидация пароля"""
        password = self.cleaned_data.get('password')
        if password:
            password = password.strip()
            if len(password) < 4:
                raise forms.ValidationError("Пароль должен содержать минимум 4 символа")
        return password


# ✏️ Форма редактирования профиля менеджера
class ProfileForm(forms.ModelForm):
    """Форма для редактирования профиля менеджера"""
    
    phone_validator = RegexValidator(
        regex=r'^\+?992\d{9}$',
        message="Введите номер в формате: +992XXXXXXXXX"
    )
    
    phone = forms.CharField(
        required=False,
        validators=[phone_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '+992XXXXXXXXX',
            'pattern': r'\+?992\d{9}'
        }),
        help_text="Формат: +992XXXXXXXXX"
    )
    
    class Meta:
        model = Profile
        fields = ['phone']
        labels = {
            'phone': '📱 Телефон',
        }
    
    def clean_phone(self):
        """Валидация номера телефона"""
        phone = self.cleaned_data.get('phone')
        if phone:
            phone = phone.strip()
            # Автоматическое добавление +992 если не указан
            if not phone.startswith('+'):
                if phone.startswith('992'):
                    phone = '+' + phone
                else:
                    phone = '+992' + phone
        return phone


# 💰 Форма пополнения баланса менеджера (только для админов)
class TopUpBalanceForm(forms.Form):
    """Форма для пополнения баланса менеджера администратором"""
    
    manager = forms.ModelChoiceField(
        queryset=Profile.objects.select_related('user').all(),
        label='👤 Выберите менеджера',
        widget=forms.Select(attrs={
            'class': 'form-select form-control',
        }),
        empty_label="-- Выберите менеджера --"
    )
    
    amount = forms.DecimalField(
        label='💵 Сумма пополнения ($)',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00',
            'step': '0.01',
            'min': '9.00'
        }),
        help_text="Введите сумму для пополнения (минимум 9$)"
    )
    
    comment = forms.CharField(
        label='📝 Комментарий',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Причина пополнения (необязательно)',
            'rows': 3
        }),
        help_text="Опишите причину пополнения баланса"
    )
    
    def clean_amount(self):
        """Валидация суммы"""
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError("Сумма должна быть больше 0")
        if amount and amount > Decimal('10000000'):
            raise forms.ValidationError("Максимальная сумма пополнения: 10,000,000$")
        return amount


# 🎁 Форма управления ручной скидкой (для администратора)
class ManualDiscountForm(forms.ModelForm):
    """Форма для выдачи ручной скидки менеджеру администратором"""
    
    class Meta:
        model = Profile
        fields = ['manual_discount_percentage']
        widgets = {
            'manual_discount_percentage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0',
                'max': '99',
            })
        }
        labels = {
            'manual_discount_percentage': '🎁 Размер ручной скидки (%)',
        }
        help_texts = {
            'manual_discount_percentage': 'Дополнительная скидка для менеджера (суммируется с автоматической). Максимум 99%.',
        }
    
    def clean_manual_discount_percentage(self):
        """Валидация размера скидки"""
        discount = self.cleaned_data.get('manual_discount_percentage')
        if discount and discount < 0:
            raise forms.ValidationError("Скидка не может быть отрицательной")
        if discount and discount > 99:
            raise forms.ValidationError("Максимальная скидка 99%")
        return discount