from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from clients.views import (
    home_view,
    add_client_view,
    clients_list_view,
    client_manager_profile_view,
    edit_profile_view,
    edit_client,
    client_settings,
    select_packages_view,
    topup_balance_view,
    balance_history_view,
    admin_topup_balance_view,
    admin_manage_discounts_view,
    sync_packages_from_dealer_view,
    logout_view,
    ports_table_view,
)

# Временная view для теста модального окна
def test_topup_modal_view(request):
    return render(request, 'test_topup_modal.html')

urlpatterns = [
    path('admin/', admin.site.urls),

    # 🔑 Авторизация
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', logout_view, name='logout'),

    # 🏠 Главная
    path('home/', home_view, name='home'),
    path('', home_view, name='root'),

    # ➕ Клиенты
    path('add-client/', add_client_view, name='add_client'),
    path('clients/', clients_list_view, name='clients_list'),
    path('clients/<int:client_id>/edit/', edit_client, name='edit_client'),

    # 💳 Купить пакет
    path("packages/", select_packages_view, name="select_packages"),
    path('clients/<int:client_id>/settings/', client_settings, name='client_settings'),
    path("profile/topup/", topup_balance_view, name="topup_balance"),
    path("profile/balance-history/", balance_history_view, name="balance_history"),
    
    # 💰 Пополнение баланса (только админы)
    path('api/topup-balance/', admin_topup_balance_view, name='admin_topup_balance'),
    path('admin/manage-discounts/', admin_manage_discounts_view, name='admin_manage_discounts'),
    
    # 🔧 Синхронизация пакетов (только админы)
    path('admin/sync-packages/', sync_packages_from_dealer_view, name='sync_packages_from_dealer'),
    
    # 📋 Таблица портов
    path('ports-table/', ports_table_view, name='ports_table'),
    
    # 👤 Профиль менеджера
    path('profile/', client_manager_profile_view, name='client_manager_profile'),
    path('profile/edit/', edit_profile_view, name='edit_profile'),

    # 🔒 Смена пароля
    path('password_change/', auth_views.PasswordChangeView.as_view(template_name='password_change.html'), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(template_name='password_change_done.html'), name='password_change_done'),
    
    # 🧪 Тест модального окна (временно)
    path('test-topup-modal/', test_topup_modal_view, name='test_topup_modal'),
]