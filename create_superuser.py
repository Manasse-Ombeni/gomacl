import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'goma_cl.settings')
django.setup()

from django.contrib.auth.models import User

username = 'ombeni'
email = 'ombenation16@gmail.com'
password = 'Goma-2026'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"Superuser '{username}' créé avec succès !")
else:
    print(f"L'utilisateur '{username}' existe déjà.")