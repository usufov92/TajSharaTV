from django.core.management.base import BaseCommand
from clients.models import Profile


class Command(BaseCommand):
    help = 'Обновляет скидки для всех менеджеров на основе количества клиентов'

    def handle(self, *args, **options):
        profiles = Profile.objects.all()
        updated_count = 0
        
        self.stdout.write("🔄 Начинаем обновление скидок...\n")
        
        for profile in profiles:
            old_discount = profile.discount_percentage
            new_discount = profile.update_discount()
            active_clients = profile.get_clients_count()
            total_clients = profile.get_total_clients_count()
            
            if old_discount != new_discount:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ {profile.user.username}: {active_clients} активных / {total_clients} всего | "
                        f"Скидка: {old_discount}% → {new_discount}%"
                    )
                )
                updated_count += 1
            else:
                self.stdout.write(
                    f"➖ {profile.user.username}: {active_clients} активных / {total_clients} всего | "
                    f"Скидка: {new_discount}% (без изменений)"
                )
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(
            self.style.SUCCESS(
                f"🎉 Готово! Обновлено скидок: {updated_count} из {profiles.count()}"
            )
        )
