#!/usr/bin/env python
import os
import django

# Set DJANGO_SETTINGS_MODULE BEFORE importing Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings_iptv')

# Setup Django
django.setup()

# Now create the superuser
from django.contrib.auth import get_user_model

User = get_user_model()

# Create superuser for IPTV instance
if not User.objects.filter(username='admin_iptv').exists():
    User.objects.create_superuser('admin_iptv', 'admin@iptv.local', 'admin123')
    print('✓ IPTV Superuser created: admin_iptv / admin123')
else:
    print('✓ IPTV Superuser already exists: admin_iptv')

# List all users in IPTV database
users = User.objects.all()
print(f'IPTV Database Users: {[u.username for u in users]}')
