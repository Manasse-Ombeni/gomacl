from django.core.management.base import BaseCommand
from core.models import Team, Match

class Command(BaseCommand):
    help = "Recalculer les stats (phase league) à partir des matchs joués"

    def handle(self, *args, **options):
        # Reset stats
        Team.objects.update(
            played=0, wins=0, draws=0, losses=0,
            goals_for=0, goals_against=0, points=0
        )

        matches = Match.objects.filter(is_played=True, phase__name='league').select_related(
            'home_team', 'away_team', 'forfeit_team', 'phase'
        )

        for m in matches:
            home = m.home_team
            away = m.away_team

            if m.is_forfeit:
                # Forfait = victoire 3-0 pour l'autre
                if m.forfeit_team_id == home.id:
                    # away gagne
                    away.played += 1
                    away.wins += 1
                    away.points += 3
                    away.goals_for += 3

                    home.played += 1
                    home.losses += 1
                    home.goals_against += 3
                else:
                    # home gagne
                    home.played += 1
                    home.wins += 1
                    home.points += 3
                    home.goals_for += 3

                    away.played += 1
                    away.losses += 1
                    away.goals_against += 3
            else:
                hs = m.home_score or 0
                as_ = m.away_score or 0

                home.played += 1
                away.played += 1

                home.goals_for += hs
                home.goals_against += as_

                away.goals_for += as_
                away.goals_against += hs

                if hs > as_:
                    home.wins += 1
                    home.points += 3
                    away.losses += 1
                elif hs < as_:
                    away.wins += 1
                    away.points += 3
                    home.losses += 1
                else:
                    home.draws += 1
                    home.points += 1
                    away.draws += 1
                    away.points += 1

            home.save()
            away.save()

        self.stdout.write(self.style.SUCCESS("OK: Classement recalculé (phase league)."))