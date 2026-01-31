"""
Скрипт для загрузки пакетов из packages.json в базу данных Django
Запустить: python manage.py shell < load_packages_to_db.py
или python manage.py shell -c "exec(open('load_packages_to_db.py').read())"
"""
import os
import json
import django

# Конфигурируем Django если нужно
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from clients.models import Package

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGES_FILE = os.path.join(BASE_DIR, 'packages.json')


def load_packages():
    """Загружает пакеты из JSON в БД"""
    try:
        with open(PACKAGES_FILE, 'r', encoding='utf-8') as f:
            packages = json.load(f)
    except FileNotFoundError:
        print(f"❌ Файл не найден: {PACKAGES_FILE}")
        return
    except json.JSONDecodeError as e:
        print(f"❌ Ошибка парсинга JSON: {e}")
        return
    
    print(f"\n📦 Загрузка {len(packages)} пакетов...\n")
    
    created_count = 0
    updated_count = 0
    
    for pkg in packages:
        try:
            # Проверяем что это акционный пакет (по префиксу "Акционный !!")
            is_promo = pkg['name'].startswith('Акционный !!')
            
            # Получаем или создаём пакет
            package, created = Package.objects.get_or_create(
                name=pkg['name'],
                defaults={
                    'price': pkg['price'],
                    'is_promo': is_promo,
                }
            )
            
            if created:
                created_count += 1
                status = "✅ СОЗДАН"
            else:
                # Обновляем цену если изменилась
                if float(package.price) != pkg['price']:
                    package.price = pkg['price']
                    package.save()
                    updated_count += 1
                    status = "🔄 ОБНОВЛЁН"
                else:
                    status = "ℹ️ СУЩЕСТВУЕТ"
            
            print(f"{status}: {pkg['name']:50s} | ${pkg['price']:6.2f}")
        
        except Exception as e:
            print(f"❌ ОШИБКА: {pkg['name']} - {e}")
    
    print(f"\n{'='*80}")
    print(f"📊 Результат:")
    print(f"   ✅ Создано:   {created_count}")
    print(f"   🔄 Обновлено: {updated_count}")
    print(f"   📦 Всего в БД: {Package.objects.count()}")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    load_packages()
