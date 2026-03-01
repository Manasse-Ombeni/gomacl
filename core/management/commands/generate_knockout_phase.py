from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import Competition, Team, Phase, Match

class Command(BaseCommand):
    help = 'Génère les phases éliminatoires (playoffs, 1/8, 1/4, 1/2, finale)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--phase',
            type=str,
            choices=['playoff', 'round_16', 'quarter', 'semi', 'final'],
            help='Type de phase à générer',
        )

    def handle(self, *args, **options):
        phase_type = options.get('phase')
        
        competition = Competition.objects.filter(is_active=True).first()
        
        if not competition:
            self.stdout.write(self.style.ERROR('❌ Aucune compétition active trouvée.'))
            return
        
        # Récupérer le classement actuel
        teams = Team.objects.filter(competition=competition).order_by('-points', '-goals_for')
        
        if phase_type == 'playoff':
            self.generate_playoffs(competition, teams)
        elif phase_type == 'round_16':
            self.generate_round_of_16(competition, teams)
        elif phase_type == 'quarter':
            self.generate_quarters(competition)
        elif phase_type == 'semi':
            self.generate_semis(competition)
        elif phase_type == 'final':
            self.generate_final(competition)
        else:
            self.stdout.write(self.style.ERROR('❌ Veuillez spécifier --phase'))
    
    def generate_playoffs(self, competition, teams):
        """Génère les barrages (9e vs 24e, 10e vs 23e, etc.)"""
        self.stdout.write(self.style.SUCCESS('📊 Génération des BARRAGES (Playoffs)'))
        
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name='playoff',
            defaults={'order': 2, 'is_active': True}
        )
        
        if not created:
            phase.matches.all().delete()
        
        # Places 9-24 vont en playoffs
        playoff_teams = list(teams[8:24])  # Indices 8 à 23 (9e à 24e)
        
        if len(playoff_teams) < 16:
            self.stdout.write(self.style.ERROR('❌ Pas assez d\'équipes qualifiées pour les playoffs.'))
            return
        
        matches_created = 0
        start_date = timezone.now() + timedelta(days=3)
        
        # 8 matchs aller-retour
        for i in range(8):
            home_team = playoff_teams[i]
            away_team = playoff_teams[15 - i]  # 9e vs 24e, 10e vs 23e, etc.
            
            # Match aller
            Match.objects.create(
                phase=phase,
                home_team=home_team,
                away_team=away_team,
                scheduled_date=start_date + timedelta(days=i)
            )
            
            # Match retour
            Match.objects.create(
                phase=phase,
                home_team=away_team,
                away_team=home_team,
                scheduled_date=start_date + timedelta(days=i + 7)
            )
            
            matches_created += 2
        
        self.stdout.write(self.style.SUCCESS(f'✅ {matches_created} matchs de playoffs créés'))
    
    def generate_round_of_16(self, competition, teams):
        """Génère les 1/8 de finale"""
        self.stdout.write(self.style.SUCCESS('📊 Génération des 1/8 DE FINALE'))
        
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name='round_16',
            defaults={'order': 3, 'is_active': True}
        )
        
        if not created:
            phase.matches.all().delete()
        
        # Top 8 + 8 gagnants des playoffs = 16 équipes
        # Pour simplifier, on prend les 16 premières équipes du classement
        qualified_teams = list(teams[:16])
        
        if len(qualified_teams) < 16:
            self.stdout.write(self.style.ERROR('❌ Pas assez d\'équipes qualifiées.'))
            return
        
        matches_created = 0
        start_date = timezone.now() + timedelta(days=3)
        
        # 8 matchs (matchs uniques)
        for i in range(8):
            home_team = qualified_teams[i]
            away_team = qualified_teams[15 - i]
            
            Match.objects.create(
                phase=phase,
                home_team=home_team,
                away_team=away_team,
                scheduled_date=start_date + timedelta(days=i)
            )
            matches_created += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ {matches_created} matchs de 1/8 créés'))
    
    def generate_quarters(self, competition):
        """Génère les quarts de finale"""
        self.stdout.write(self.style.SUCCESS('📊 Génération des QUARTS DE FINALE'))
        
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name='quarter',
            defaults={'order': 4, 'is_active': True}
        )
        
        # Récupérer les gagnants des 1/8
        round_16_phase = Phase.objects.filter(competition=competition, name='round_16').first()
        
        if not round_16_phase:
            self.stdout.write(self.style.ERROR('❌ Les 1/8 de finale n\'ont pas été générés.'))
            return
        
        # Pour l'instant, on crée juste les emplacements
        # Les équipes seront ajoutées manuellement après les 1/8
        self.stdout.write(self.style.WARNING('⚠️ Les quarts seront créés après les 1/8'))
    
    def generate_semis(self, competition):
        """Génère les demi-finales"""
        self.stdout.write(self.style.SUCCESS('📊 Génération des DEMI-FINALES'))
        
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name='semi',
            defaults={'order': 5, 'is_active': True}
        )
        
        self.stdout.write(self.style.WARNING('⚠️ Les demi-finales seront créées après les quarts'))
    
    def generate_final(self, competition):
        """Génère la finale"""
        self.stdout.write(self.style.SUCCESS('📊 Génération de la FINALE'))
        
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name='final',
            defaults={'order': 6, 'is_active': True}
        )
        
        self.stdout.write(self.style.WARNING('⚠️ La finale sera créée après les demi-finales'))