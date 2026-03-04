from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Crée le superuser ombeni si il n\'existe pas'

    def handle(self, *args, **options):
        username = 'ombeni'
        email = 'ombenimanasse@gmail.com'
        password = 'GomaCL2026@Secure!'

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' créé avec succès !"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' existe déjà."))