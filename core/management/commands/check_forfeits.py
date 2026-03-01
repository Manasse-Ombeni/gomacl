from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Match

class Command(BaseCommand):
    help = 'Affiche les matchs en retard (plus de 48h) sans appliquer de forfait automatique'

    def handle(self, *args, **options):
        now = timezone.now()
        deadline = now - timedelta(hours=48)
        
        # Récupérer les matchs non joués dont la date prévue est passée de plus de 48h
        late_matches = Match.objects.filter(
            is_played=False,
            is_forfeit=False,
            scheduled_date__lt=deadline
        )
        
        if late_matches.exists():
            self.stdout.write(
                self.style.WARNING(f'\n⚠️ {late_matches.count()} match(s) en retard (plus de 48h)\n')
            )
            
            for match in late_matches:
                hours_late = (now - match.scheduled_date).total_seconds() / 3600
                
                self.stdout.write(
                    self.style.WARNING(
                        f'  • {match.home_team.abbreviation} vs {match.away_team.abbreviation} '
                        f'(prévu le {match.scheduled_date.strftime("%d/%m/%Y %H:%M")}) '
                        f'- Retard: {int(hours_late)}h'
                    )
                )
                
                if match.reported:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'    ✅ Signalé par {match.reported_by.abbreviation}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f'    ❌ Non signalé'
                        )
                    )
            
            self.stdout.write(
                self.style.WARNING(
                    f'\n💡 Aucun forfait automatique appliqué.'
                    f'\n   L\'admin doit décider manuellement sur : /dashboard/reported-matches/\n'
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Aucun match en retard'))