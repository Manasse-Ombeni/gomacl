from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta, datetime
import random
from collections import defaultdict
from core.models import Competition, Team, Phase, Match


class Command(BaseCommand):
    help = "Génère le calendrier de la phase de ligue (max 2 matchs par jour par équipe, début demain à 00:00)"

    def handle(self, *args, **options):

        competition = Competition.objects.filter(is_active=True).first()

        if not competition:
            self.stdout.write(self.style.ERROR("❌ Aucune compétition active trouvée."))
            return

        teams = list(
            Team.objects.filter(
                competition=competition,
                payment_validated=True
            )
        )

        if len(teams) != 36:
            self.stdout.write(self.style.ERROR("❌ Il faut exactement 36 équipes validées."))
            return

        # ✅ Création ou récupération de la phase de ligue
        phase, created = Phase.objects.get_or_create(
            competition=competition,
            name="league",
            defaults={"order": 1, "is_active": True},
        )

        if not created:
            phase.matches.all().delete()
            self.stdout.write(self.style.WARNING("🗑️ Anciens matchs supprimés"))

        self.stdout.write(self.style.SUCCESS("📊 Génération du calendrier..."))

        # ✅ Début = demain à 00:00
        now = timezone.now()
        tomorrow = now.date() + timedelta(days=1)

        start_date = timezone.make_aware(
            datetime.combine(tomorrow, datetime.min.time())
        )

        # ✅ Chaque équipe doit jouer 8 matchs
        matches_needed = {team.id: 8 for team in teams}

        # ✅ Compteur de matchs par jour par équipe
        matches_per_day = defaultdict(lambda: defaultdict(int))

        matches_created = 0
        current_date = start_date

        # ✅ Boucle principale
        while any(v > 0 for v in matches_needed.values()):

            random.shuffle(teams)

            for i in range(0, len(teams), 2):
                if i + 1 >= len(teams):
                    continue

                team1 = teams[i]
                team2 = teams[i + 1]

                # ✅ Vérifier qu'ils ont encore besoin de matchs
                if matches_needed[team1.id] == 0 or matches_needed[team2.id] == 0:
                    continue

                # ✅ Vérifier limite 2 matchs par jour
                if matches_per_day[current_date.date()][team1.id] >= 2:
                    continue

                if matches_per_day[current_date.date()][team2.id] >= 2:
                    continue

                # ✅ Vérifier qu'ils ne se sont pas déjà affrontés
                existing = Match.objects.filter(
                    phase=phase,
                    home_team__in=[team1, team2],
                    away_team__in=[team1, team2]
                ).exists()

                if existing:
                    continue

                # ✅ Domicile aléatoire
                if random.choice([True, False]):
                    home, away = team1, team2
                else:
                    home, away = team2, team1

                Match.objects.create(
                    phase=phase,
                    home_team=home,
                    away_team=away,
                    scheduled_date=current_date
                )

                # ✅ Mise à jour des compteurs
                matches_needed[team1.id] -= 1
                matches_needed[team2.id] -= 1

                matches_per_day[current_date.date()][team1.id] += 1
                matches_per_day[current_date.date()][team2.id] += 1

                matches_created += 1

            # ✅ Passer au jour suivant
            current_date += timedelta(days=1)

        self.stdout.write(self.style.SUCCESS(f"✅ {matches_created} matchs créés"))
        self.stdout.write(self.style.SUCCESS("📅 Début : demain à 00:00"))
        self.stdout.write(self.style.SUCCESS("⚽ Max 2 matchs/jour par équipe respecté"))