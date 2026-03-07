# core/signals.py
from django.core.management import call_command
from django.db import transaction
from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver

from .models import Match


TRACK_FIELDS = [
    "is_played", "is_forfeit",
    "home_score", "away_score",
    "home_extra_time", "away_extra_time",
    "home_penalties", "away_penalties",
    "forfeit_team_id",
]

def _schedule_recalc():
    # Lance après commit DB (plus sûr)
    transaction.on_commit(lambda: call_command("recalc_league_table"))


@receiver(pre_save, sender=Match)
def match_pre_save(sender, instance: Match, **kwargs):
    if not instance.pk:
        instance._old_values = None
        return

    old = Match.objects.filter(pk=instance.pk).values(
        *TRACK_FIELDS, "phase__name"
    ).first()
    instance._old_values = old


@receiver(post_save, sender=Match)
def match_post_save(sender, instance: Match, created, **kwargs):
    # Ignorer si pas phase
    if not instance.phase_id:
        return

    # On ne recalcule que pour la league
    if instance.phase.name != "league":
        return

    # Création d'un match non joué => pas besoin
    if created and not instance.is_played:
        return

    old = getattr(instance, "_old_values", None)

    # Si on ne connait pas l’ancien état, on recalcule
    if not old:
        _schedule_recalc()
        return

    # Si un champ important a changé => recalcul
    if old.get("phase__name") != "league":
        _schedule_recalc()
        return

    for f in TRACK_FIELDS:
        if old.get(f) != getattr(instance, f):
            _schedule_recalc()
            return


@receiver(post_delete, sender=Match)
def match_post_delete(sender, instance: Match, **kwargs):
    if instance.phase_id and instance.phase.name == "league":
        _schedule_recalc()