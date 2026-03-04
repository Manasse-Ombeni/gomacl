from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = "Crée le superuser ombeni automatiquement"

    def handle(self, *args, **options):
        username = 'ombeni'
        email = 'ombenation16@gmail.com'
        password = 'Goma-2026'

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' créé !"))
        else:
            self.stdout.write("Superuser existe déjà.")