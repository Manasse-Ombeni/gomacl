import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'goma_cl.settings')
django.setup()

from django.contrib.auth.models import User

# Créer le superuser par défaut
username = 'ombeni'
password = '1234'
email = 'admin@gomacl.com'

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password)
    print(f"✅ Superuser '{username}' créé avec succès !")
else:
    print(f"⚠️ L'utilisateur '{username}' existe déjà.")