import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'goma_cl.settings')
django.setup()

from django.contrib.auth.models import User

# Créer le superuser en production
username = 'ombeni'
password = 'Goma-2026'  # Mot de passe sécurisé pour la production
email = 'ombenation16@gmail.com'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✅ Superuser '{username}' créé avec succès !")
else:
    print(f"⚠️ L'utilisateur '{username}' existe déjà.")