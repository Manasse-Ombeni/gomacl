from django.core.management.base import BaseCommand
from core.models import Competition, Team, Phase, Match

class Command(BaseCommand):
    help = 'Réinitialise toutes les statistiques de la compétition'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirmer la réinitialisation',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    '⚠️ Cette commande va réinitialiser TOUTES les statistiques.\n'
                    'Utilisez --confirm pour confirmer.'
                )
            )
            return
        
        # Réinitialiser les stats de toutes les équipes
        teams = Team.objects.all()
        for team in teams:
            team.played = 0
            team.wins = 0
            team.draws = 0
            team.losses = 0
            team.goals_for = 0
            team.goals_against = 0
            team.points = 0
            team.save()
        
        self.stdout.write(self.style.SUCCESS(f'✅ {teams.count()} équipes réinitialisées'))
        
        # Supprimer tous les matchs
        matches_count = Match.objects.count()
        Match.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'✅ {matches_count} matchs supprimés'))
        
        # Supprimer toutes les phases sauf la phase de ligue
        phases_deleted = Phase.objects.exclude(name='league').delete()[0]
        self.stdout.write(self.style.SUCCESS(f'✅ {phases_deleted} phases supprimées'))
        
        self.stdout.write(self.style.SUCCESS('\n🎉 Compétition réinitialisée avec succès !'))