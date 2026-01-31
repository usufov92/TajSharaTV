from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Client

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)  # ✅ гарантируем наличие профиля


@receiver(post_save, sender=Client)
def update_manager_discount(sender, instance, created, **kwargs):
    """Автоматически обновляет скидку менеджера при добавлении/изменении клиента"""
    if instance.created_by:
        try:
            profile = instance.created_by.profile
            old_discount = profile.discount_percentage
            new_discount = profile.update_discount()
            
            # Если скидка изменилась, можно добавить логирование
            if old_discount != new_discount:
                active_count = profile.get_clients_count()
                print(f"✅ Скидка менеджера {instance.created_by.username} обновлена: {old_discount}% → {new_discount}% ({active_count} активных клиентов)")
        except Profile.DoesNotExist:
            Profile.objects.create(user=instance.created_by)