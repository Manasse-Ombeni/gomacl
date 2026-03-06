from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .decorators import role_required   # ← Ligne magique
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Q, F
from django.utils import timezone
from .models import Team, Competition, Phase, Match, Group, News, UserProfile
from .forms import TeamRegistrationForm, MatchResultForm
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from django.core.management import call_command
from io import StringIO
from datetime import datetime, timedelta
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from .forms import CompetitionForm
from django.contrib.auth.forms import UserCreationForm
from functools import wraps
from .models import AdminLog
import os
from django.views.decorators.http import require_GET
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.db import transaction
from django.http import JsonResponse
from django.db import connection
import random
from django.db.models import Count, Q




# ==========================================
# PAGE D'ACCUEIL
# ==========================================
def home(request):
    """
    Page d'accueil du site
    """
    # Récupérer la compétition active
    competition = Competition.objects.filter(is_active=True).first()
    
    # Top 8 équipes (seulement celles validées)
    top_teams = Team.objects.filter(payment_validated=True).annotate(
        diff_buts=F('goals_for') - F('goals_against')
    ).order_by('-points', '-diff_buts', '-goals_for')[:8]
    
    # Prochains matchs (3 prochains)
    upcoming_matches = Match.objects.filter(
        is_played=False,
        scheduled_date__gte=timezone.now()
    ).order_by('scheduled_date')[:3]
    
    # Dernières actualités
    latest_news = News.objects.filter(is_published=True).order_by('-created_at')[:3]
    
    context = {
        'competition': competition,
        'top_teams': top_teams,
        'upcoming_matches': upcoming_matches,
        'latest_news': latest_news,
    }
    return render(request, 'core/home.html', context)


# ==========================================
# INSCRIPTION D'UN JOUEUR (AVEC PAIEMENT)
# ==========================================
def register_team(request):
    """
    Page d'inscription pour un nouveau joueur/équipe avec paiement
    """
    competition = Competition.objects.filter(is_active=True, registration_open=True).first()
    
    if not competition:
        messages.error(request, _("Les inscriptions sont fermées."))
        return redirect('home')
    
    if competition.is_registration_full:
        messages.error(request, _(f"Le nombre maximum d'équipes ({competition.max_teams}) a été atteint."))
        return redirect('home')
    
    if request.method == 'POST':
        form = TeamRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            team = form.save(commit=False)
            
            # Créer un utilisateur pour ce joueur
            username = form.cleaned_data['abbreviation'].lower()
            password = form.cleaned_data['password']
            
            # Vérifier si le username existe déjà
            if User.objects.filter(username=username).exists():
                messages.error(request, _(f"L'abréviation {username} est déjà utilisée comme nom d'utilisateur."))
                return render(request, 'core/register_team.html', {
                    'form': form, 
                    'competition': competition,
                    'remaining_slots': competition.max_teams - competition.registered_teams_count,
                })
            
            # Créer l'utilisateur
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=form.cleaned_data['player_name'],
                email=f"{username}@gomacl.local"
            )
            
            team.user = user
            team.competition = competition
            team.payment_validated = False  # En attente de validation
            team.save()
            
            messages.success(
                request,
                "✅ Inscription réussie ! Rejoignez le groupe WhatsApp et envoyez la preuve de paiement pour validation."
            )
            
            # Envoyer notification à l'admin (optionnel)
            # send_admin_notification(team)
            
            return redirect('home')
        else:
            messages.error(request, _("Inscription refusée : corrige les champs en rouge puis réessaie."))
    else:
        form = TeamRegistrationForm()
    
    context = {
        'form': form,
        'competition': competition,
        'remaining_slots': competition.max_teams - competition.registered_teams_count if competition else 0,
    }
    return render(request, 'core/register_team.html', context)


# ==========================================
# LISTE DES ÉQUIPES
# ==========================================
def teams_list(request):
    """
    Afficher toutes les équipes inscrites et validées
    """
    teams = Team.objects.filter(payment_validated=True)
    
    context = {
        'teams': teams,
    }
    return render(request, 'core/teams_list.html', context)


# ==========================================
# CLASSEMENT GÉNÉRAL
# ==========================================
def standings(request):
    """
    Classement général (phase de ligue)
    """
    teams = Team.objects.filter(payment_validated=True).annotate(
        diff_buts=F('goals_for') - F('goals_against')
    ).order_by('-points', '-diff_buts', '-goals_for')
    
    context = {
        'teams': teams,
    }
    return render(request, 'core/standings.html', context)


# ==========================================
# CALENDRIER DES MATCHS
# ==========================================
def fixtures(request):
    """
    Calendrier de tous les matchs
    """
    competition = Competition.objects.filter(is_active=True).first()
    
    if competition:
        phases = Phase.objects.filter(competition=competition).prefetch_related('matches')
    else:
        phases = []
    
    context = {
        'competition': competition,
        'phases': phases,
    }
    return render(request, 'core/fixtures.html', context)


# ==========================================
# RÉSULTATS DES MATCHS
# ==========================================
def results(request):
    """
    Tous les résultats des matchs joués
    """
    played_matches = Match.objects.filter(is_played=True).order_by('-played_date')
    
    context = {
        'matches': played_matches,
    }
    return render(request, 'core/results.html', context)


# ==========================================
# TABLEAU ÉLIMINATOIRE (BRACKET)
# ==========================================
def bracket(request):
    competition = Competition.objects.filter(is_active=True).first()
    
    if competition:
        round_16 = Match.objects.filter(
            phase__name='round_16',
            phase__competition=competition
        ).order_by('scheduled_date')
        
        quarters = Match.objects.filter(
            phase__name='quarter',
            phase__competition=competition
        ).order_by('scheduled_date')
        
        semis = Match.objects.filter(
            phase__name='semi',
            phase__competition=competition
        ).order_by('scheduled_date')
        
        final = Match.objects.filter(
            phase__name='final',
            phase__competition=competition
        ).first()
    else:
        round_16 = quarters = semis = final = None
    
    return render(request, 'core/bracket.html', {
        'competition': competition,
        'round_16': round_16,
        'quarters': quarters,
        'semis': semis,
        'final': final,
    })

# ==========================================
# RÈGLEMENT
# ==========================================
def rules(request):
    """
    Règlement de la compétition
    """
    competition = Competition.objects.filter(is_active=True).first()
    
    context = {
        'competition': competition,
    }
    return render(request, 'core/rules.html', context)


# ==========================================
# À PROPOS
# ==========================================
def about(request):
    """
    Page À propos (organisateurs)
    """
    organizers = [
        {'name': 'Manassé Ombeni', 'role': _('Organisateur principal')},
        {'name': 'Job Badesire', 'role': _('Co-organisateur')},
        {'name': 'Héritier DJO', 'role': _('Co-organisateur')},
        {'name': 'Joachim', 'role': _('Co-organisateur')},
        {'name': 'Ildephonse', 'role': _('Co-organisateur')},
    ]
    
    context = {
        'organizers': organizers,
    }
    return render(request, 'core/about.html', context)


# ==========================================
# ACTUALITÉS
# ==========================================
def news_list(request):
    """
    Liste des actualités
    """
    news = News.objects.filter(is_published=True)
    
    context = {
        'news': news,
    }
    return render(request, 'core/news_list.html', context)


def news_detail(request, pk):
    """
    Détail d'une actualité
    """
    news = get_object_or_404(News, pk=pk, is_published=True)
    
    context = {
        'news': news,
    }
    return render(request, 'core/news_detail.html', context)


# =CONNEXION=========================================
def user_login(request):
    """
    Page de connexion
    """
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, _("Connexion réussie !"))
            
            # ✅ Redirection selon rôle personnalisé
            if hasattr(user, 'userprofile') and user.userprofile.role in [
                'superadmin',
                'organisateur',
                'paiement',
                'match'
            ]:
                return redirect('dashboard')
            else:
                return redirect('my_matches')

        else:
            messages.error(request, _("Nom d'utilisateur ou mot de passe incorrect."))
    
    return render(request, 'core/login.html')

# ==========================================
# DÉCONNEXION
# ==========================================
def user_logout(request):
    """
    Déconnexion
    """
    logout(request)
    messages.success(request, _("Vous êtes déconnecté."))
    return redirect('home')


# ==========================================
# DASHBOARD ADMIN
# ==========================================
@login_required
def dashboard(request):

    # ✅ Vérifier rôle autorisé
    if not hasattr(request.user, 'userprofile'):
        return redirect('home')

    if request.user.userprofile.role not in [
        'superadmin',
        'organisateur',
        'paiement',
        'match'
    ]:
        messages.error(request, "Accès refusé.")
        return redirect('home')

    # ✅ Statistiques
    total_teams = Team.objects.filter(payment_validated=True).count()
    pending_teams = Team.objects.filter(payment_validated=False).count()
    total_matches = Match.objects.count()
    played_matches = Match.objects.filter(is_played=True).count()

    return render(request, 'core/dashboard.html', {
        'total_teams': total_teams,
        'pending_teams': pending_teams,
        'total_matches': total_matches,
        'played_matches': played_matches,
    })


# ==========================================
# ENCODER UN RÉSULTAT (ADMIN)
# ==========================================
@login_required
def encode_result(request, match_id):

    # ✅ Vérification par rôle personnalisé
    if not hasattr(request.user, 'userprofile') or request.user.userprofile.role not in [
        'superadmin',
        'organisateur',
        'match'
    ]:
        messages.error(request, _("Accès refusé."))
        return redirect('home')
    
    match = get_object_or_404(Match, pk=match_id)
    
    if request.method == 'POST':
        form = MatchResultForm(request.POST, request.FILES, instance=match)
        if form.is_valid():
            match = form.save(commit=False)
            match.is_played = True
            match.played_date = timezone.now()
            match.save()
            
            # ✅ Mise à jour des stats UNIQUEMENT pour la phase de ligue
            if match.phase.name == 'league':
                update_team_stats(match)
            
            messages.success(request, _("Résultat enregistré avec succès !"))
            return redirect('dashboard')
    else:
        form = MatchResultForm(instance=match)
    
    return render(request, 'core/encode_result.html', {
        'form': form,
        'match': match,
    })

# ==========================================
# FONCTION : METTRE À JOUR LES STATS
# ==========================================
def update_team_stats(match):
    """
    Met à jour les statistiques des équipes
    ⚠️ Utilisé uniquement pour la phase de ligue
    """
    home_team = match.home_team
    away_team = match.away_team
    
    if match.is_forfeit:
        if match.forfeit_team == home_team:
            away_team.wins += 1
            away_team.points += 3
            away_team.goals_for += 3
            away_team.played += 1
            
            home_team.losses += 1
            home_team.goals_against += 3
            home_team.played += 1
        else:
            home_team.wins += 1
            home_team.points += 3
            home_team.goals_for += 3
            home_team.played += 1
            
            away_team.losses += 1
            away_team.goals_against += 3
            away_team.played += 1
    else:
        home_team.played += 1
        away_team.played += 1
        
        home_team.goals_for += match.home_score
        home_team.goals_against += match.away_score
        
        away_team.goals_for += match.away_score
        away_team.goals_against += match.home_score
        
        if match.home_score > match.away_score:
            home_team.wins += 1
            home_team.points += 3
            away_team.losses += 1
        elif match.home_score < match.away_score:
            away_team.wins += 1
            away_team.points += 3
            home_team.losses += 1
        else:
            home_team.draws += 1
            away_team.draws += 1
            home_team.points += 1
            away_team.points += 1
    
    home_team.save()
    away_team.save()


# ==========================================
# MES MATCHS (POUR LES JOUEURS)
# ==========================================
@login_required
def my_matches(request):
    """
    Afficher les matchs de l'utilisateur connecté
    """
    # Récupérer l'équipe de l'utilisateur
    try:
        team = Team.objects.get(user=request.user)
    except Team.DoesNotExist:
        messages.error(request, _("Vous n'avez pas d'équipe associée."))
        return redirect('home')
    
    # Vérifier si le paiement est validé
    if not team.payment_validated:
        messages.warning(request, _("Votre inscription est en attente de validation du paiement."))
    
    # Récupérer tous les matchs de cette équipe
    upcoming_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        is_played=False
    ).order_by('scheduled_date')
    
    played_matches = Match.objects.filter(
        Q(home_team=team) | Q(away_team=team),
        is_played=True
    ).order_by('-played_date')[:10]
    
    context = {
        'team': team,
        'upcoming_matches': upcoming_matches,
        'played_matches': played_matches,
    }
    return render(request, 'core/my_matches.html', context)


# ==========================================
# SIGNALER UN PROBLÈME
# ==========================================
@login_required
def report_match(request, match_id):
    """
    Signaler un problème sur un match
    """
    match = get_object_or_404(Match, pk=match_id)
    
    # Vérifier que l'utilisateur est bien impliqué dans ce match
    try:
        team = Team.objects.get(user=request.user)
    except Team.DoesNotExist:
        messages.error(request, _("Vous n'avez pas d'équipe associée."))
        return redirect('home')
    
    if match.home_team != team and match.away_team != team:
        messages.error(request, _("Vous n'êtes pas impliqué dans ce match."))
        return redirect('my_matches')
    
    # Vérifier que le match n'est pas déjà joué
    if match.is_played:
        messages.error(request, _("Ce match a déjà été joué."))
        return redirect('my_matches')
    
    if request.method == 'POST':
        reason = request.POST.get('reason')
        details = request.POST.get('details', '')
        
        match.reported = True
        match.reported_by = team
        match.report_reason = reason
        match.report_details = details
        match.report_date = timezone.now()
        match.save()
        
        messages.success(request, _("Signalement envoyé avec succès. L'admin va examiner votre demande."))
        return redirect('my_matches')
    
    context = {
        'match': match,
        'team': team,
    }
    return render(request, 'core/report_match.html', context)


# ==========================================
# MATCHS SIGNALÉS (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'match'])
def reported_matches(request):

    reported = Match.objects.filter(
        reported=True,
        is_played=False
    ).order_by('report_date')

    deadline = timezone.now() - timedelta(hours=48)

    late_matches = Match.objects.filter(
        is_played=False,
        is_forfeit=False,
        scheduled_date__lt=deadline
    ).exclude(reported=True).order_by('scheduled_date')

    return render(request, 'core/reported_matches.html', {
        'reported_matches': reported,
        'late_matches': late_matches,
    })


# ==========================================
# APPLIQUER UN FORFAIT (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'match'])
def apply_forfeit_manual(request, match_id):

    match = get_object_or_404(Match, pk=match_id)

    if request.method == 'POST':
        forfeit_team_id = request.POST.get('forfeit_team')
        forfeit_team = get_object_or_404(Team, pk=forfeit_team_id)

        match.is_forfeit = True
        match.is_played = True
        match.forfeit_team = forfeit_team
        match.played_date = timezone.now()

        if forfeit_team == match.home_team:
            match.home_score = 0
            match.away_score = 3
        else:
            match.home_score = 3
            match.away_score = 0

        match.save()
        update_team_stats(match)

        return redirect('reported_matches')

    return render(request, 'core/apply_forfait.html', {
        'match': match,
    })

# ==========================================
# ACTIONS ADMIN : GÉNÉRER LE CALENDRIER
# ==========================================
@role_required(['superadmin', 'organisateur'])
def generate_calendar(request):
    call_command('generate_league_phase')
    messages.success(request, "Calendrier généré avec succès !")
    return redirect('dashboard')


# ==========================================
# ACTIONS ADMIN : VÉRIFIER LES FORFAITS
# ==========================================
@role_required(['superadmin', 'organisateur'])
def check_forfeits_view(request):

    from io import StringIO

    out = StringIO()

    call_command('check_forfeits', stdout=out)

    messages.success(request, "Vérification terminée.")
    return redirect('dashboard')


# ==========================================
# ACTIONS ADMIN : GÉNÉRER LES PLAYOFFS
# ==========================================
@role_required(['superadmin', 'organisateur'])
def generate_playoffs_view(request):
    call_command('generate_knockout_phase', '--phase', 'playoff')
    messages.success(request, "Phase finale générée avec succès !")
    return redirect('dashboard')


# ==========================================
# ACTIONS ADMIN : RÉINITIALISER LA COMPÉTITION
# ==========================================
@role_required(['superadmin'])
def reset_competition_view(request):

    if request.method == 'POST':
        call_command('reset_competition', '--confirm')
        messages.warning(request, "Compétition réinitialisée.")
        return redirect('dashboard')

    return render(request, 'core/confirm_reset.html')


# ==========================================
# VALIDATION DES PAIEMENTS (ADMIN)
# ==========================================
@role_required(['superadmin', 'organisateur', 'paiement'])
def pending_payments(request):

    pending_teams = Team.objects.filter(
        payment_validated=False
    ).order_by('-created_at')

    return render(request, 'core/pending_payments.html', {
        'pending_teams': pending_teams,
    })


@role_required(['superadmin', 'organisateur', 'paiement'])
def validate_payment(request, team_id):

    team = get_object_or_404(Team, pk=team_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            team.payment_validated = True
            team.payment_validated_by = request.user
            team.payment_validated_at = timezone.now()
            team.save()

            AdminLog.objects.create(
                user=request.user,
                action=f"Validation paiement {team.team_name}"
            )

        elif action == 'reject':
            team.delete()

        return redirect('pending_payments')

    return render(request, 'core/validate_payment.html', {
        'team': team,
    })


@login_required
def download_calendar_pdf(request):
    if not request.user.is_staff:
        return redirect('home')

    competition = Competition.objects.filter(is_active=True).first()
    phases = Phase.objects.filter(competition=competition).prefetch_related('matches')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="calendrier_goma_cl.pdf"'

    p = canvas.Canvas(response, pagesize=A4)
    width, height = A4

    y = height - 40
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, competition.name)
    y -= 30

    p.setFont("Helvetica", 10)

    for phase in phases:
        p.drawString(50, y, phase.get_name_display())
        y -= 20

        for match in phase.matches.all():
            line = f"{match.scheduled_date.strftime('%d/%m/%Y %H:%M')} - {match.home_team.team_name} vs {match.away_team.team_name}"
            p.drawString(60, y, line)
            y -= 15

            if y < 50:
                p.showPage()
                p.setFont("Helvetica", 10)
                y = height - 40

        y -= 10

    p.save()
    return response


@login_required
def backup_database(request):
    if not request.user.is_staff:
        return redirect('home')

    response = HttpResponse(content_type='application/json')
    filename = f"backup_gomacl_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    output = StringIO()
    call_command('dumpdata', stdout=output)
    response.write(output.getvalue())

    return response



def download_rules_pdf(request):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()
    elements = []

    title_style = styles["Heading1"]
    normal_style = styles["Normal"]

    elements.append(Paragraph("GOMA CHAMPIONS LEAGUE 2026", title_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph("REGLEMENT OFFICIEL", styles["Heading2"]))
    elements.append(Spacer(1, 0.5 * inch))

    content = render_to_string("core/rules_pdf_content.html")

    for line in content.split("\n"):
        elements.append(Paragraph(line, normal_style))
        elements.append(Spacer(1, 0.2 * inch))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Reglement_GomaCL_{datetime.now().strftime("%Y%m%d")}.pdf"'

    return response


@role_required(['superadmin', 'organisateur'])
def manage_competition(request):
    competition = Competition.objects.first()
    return render(request, 'core/manage_competition.html', {
        'competition': competition
    })

@role_required(['superadmin', 'organisateur'])
def manage_teams(request):
    teams = Team.objects.all()
    return render(request, 'core/manage_teams.html', {
        'teams': teams
    })

@role_required(['superadmin', 'organisateur', 'match'])
def manage_matches(request):
    matches = Match.objects.all().order_by('-scheduled_date')
    return render(request, 'core/manage_matches.html', {
        'matches': matches
    })

@role_required(['superadmin', 'organisateur'])
def competition_list(request):
    competitions = Competition.objects.all()
    return render(request, 'core/admin/competition_list.html', {
        'competitions': competitions
    })


@role_required(['superadmin', 'organisateur'])
def competition_create(request):
    form = CompetitionForm(request.POST or None)
    if form.is_valid():
        form.save()
        messages.success(request, "Compétition créée avec succès !")
        return redirect('competition_list')
    return render(request, 'core/admin/competition_form.html', {
        'form': form,
        'title': 'Créer une compétition'
    })


@role_required(['superadmin', 'organisateur'])
def competition_edit(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    form = CompetitionForm(request.POST or None, instance=competition)
    if form.is_valid():
        form.save()
        messages.success(request, "Compétition modifiée avec succès !")
        return redirect('competition_list')
    return render(request, 'core/admin/competition_form.html', {
        'form': form,
        'title': 'Modifier la compétition'
    })


@role_required(['superadmin', 'organisateur'])
def competition_delete(request, pk):
    competition = get_object_or_404(Competition, pk=pk)
    competition.delete()
    messages.success(request, "Compétition supprimée.")
    return redirect('competition_list')

@role_required(['superadmin', 'organisateur'])
def team_list(request):
    teams = Team.objects.all()
    return render(request, 'core/admin/team_list.html', {
        'teams': teams
    })


@role_required(['superadmin', 'organisateur'])
def team_delete(request, pk):
    team = get_object_or_404(Team, pk=pk)
    team.delete()
    messages.success(request, "Équipe supprimée avec succès.")
    return redirect('team_list')


@login_required
def edit_my_team(request):
    team = get_object_or_404(Team, user=request.user)

    form = TeamRegistrationForm(request.POST or None, instance=team)

    if form.is_valid():
        form.save()
        return redirect('my_matches')

    return render(request, 'core/edit_my_team.html', {
        'form': form
    })

@role_required(['superadmin', 'organisateur'])
def edit_team(request, pk):
    team = get_object_or_404(Team, pk=pk)
    form = TeamRegistrationForm(request.POST or None, instance=team)
    if form.is_valid():
        form.save()
        messages.success(request, "Équipe modifiée avec succès !")
        return redirect('team_list')
    return render(request, 'core/admin/edit_team.html', {
        'form': form,
        'title': 'Modifier équipe'
    })


@role_required('superadmin')
def manage_users(request):
    users = UserProfile.objects.select_related('user')
    return render(request, 'core/admin/manage_users.html', {
        'users': users,
        'title': 'Gestion des utilisateurs'
    })


@role_required('superadmin')
def create_user(request):
    form = UserCreationForm(request.POST or None)

    if form.is_valid():
        user = form.save()
        return redirect('manage_users')

    return render(request, 'core/admin/user_form.html', {
        'form': form,
        'title': 'Créer utilisateur'
    })


@role_required('superadmin')
def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    profile = user.userprofile

    if request.method == 'POST':
        role = request.POST.get('role')
        profile.role = role
        profile.save()
        return redirect('manage_users')

    return render(request, 'core/admin/edit_user.html', {
        'user_obj': user,
        'profile': profile,
        'title': 'Modifier utilisateur'
    })


@role_required('superadmin')
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.delete()
    return redirect('manage_users')


@login_required
def admin_logs(request):
    if not request.user.is_staff:
        return redirect('home')

    logs = AdminLog.objects.all().order_by('-timestamp')

    return render(request, 'core/admin/logs.html', {
        'logs': logs
    })


@role_required(['superadmin'])
def edit_user_role(request, user_id):

    user = get_object_or_404(User, pk=user_id)
    profile = user.userprofile

    if request.method == 'POST':
        new_role = request.POST.get('role')
        profile.role = new_role
        profile.save()
        return redirect('team_list')

    return render(request, 'core/admin/edit_user_role.html', {
        'user_obj': user,
        'profile': profile,
        'title': 'Modifier rôle utilisateur'
    })




@require_GET
def temp_create_admin(request):
    """
    Crée / met à jour un superuser via une URL protégée par token.
    À utiliser une seule fois, puis désactiver via env var ou supprimer la route.
    """

    # 1) Kill switch (désactivation globale)
    if os.getenv("ADMIN_BOOTSTRAP_ENABLED", "0") != "1":
        return HttpResponseForbidden("Bootstrap admin désactivé.")

    # 2) Vérification token (obligatoire)
    token = request.GET.get("token")
    expected = os.getenv("ADMIN_BOOTSTRAP_TOKEN")
    if not expected:
        return HttpResponseForbidden("ADMIN_BOOTSTRAP_TOKEN non défini.")
    if not token or token != expected:
        return HttpResponseForbidden("Token invalide.")

    # 3) Récupérer identifiants depuis variables d'environnement
    username = os.getenv("DJANGO_SUPERUSER_USERNAME")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

    if not username or not password:
        return HttpResponseBadRequest("Variables DJANGO_SUPERUSER_USERNAME/PASSWORD manquantes.")

    # 4) Créer ou mettre à jour l'utilisateur + profil
    with transaction.atomic():
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        # IMPORTANT: ton signal post_save crée UserProfile automatiquement à la création.
        # Si tu veux forcer le rôle superadmin :
        if hasattr(user, "userprofile"):
            user.userprofile.role = "superadmin"
            user.userprofile.save()

    return HttpResponse(
        f"""
        <h2>OK</h2>
        <p>Superuser prêt.</p>
        <ul>
          <li>username: <b>{user.username}</b></li>
          <li>created: <b>{created}</b></li>
          <li>is_superuser: <b>{user.is_superuser}</b></li>
          <li>role: <b>{getattr(user.userprofile, 'role', 'N/A')}</b></li>
        </ul>
        <p>Tu peux maintenant te connecter sur <a href="/admin/">/admin/</a>.</p>
        """
    )



@login_required
def db_check(request):
    # autoriser seulement superadmin
    if not hasattr(request.user, "userprofile") or request.user.userprofile.role != "superadmin":
        return JsonResponse({"error": "forbidden"}, status=403)

    # infos DB + dernier team
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        db_name = cursor.fetchone()[0]

    last_team = Team.objects.order_by("-created_at").values(
        "id", "team_name", "abbreviation", "whatsapp", "payment_validated", "created_at"
    ).first()

    return JsonResponse({
        "db_name": db_name,
        "teams_total": Team.objects.count(),
        "teams_pending": Team.objects.filter(payment_validated=False).count(),
        "last_team": last_team,
    }, json_dumps_params={"ensure_ascii": False, "indent": 2})


@role_required(['superadmin', 'organisateur'])
def reset_user_password(request, user_id):
    user_obj = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        new_password = (request.POST.get('new_password') or '').strip()

        if len(new_password) < 4:
            messages.error(request, "Mot de passe trop court (minimum 4 caractères).")
            return redirect('reset_user_password', user_id=user_id)

        user_obj.set_password(new_password)
        user_obj.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Reset mot de passe pour {user_obj.username}"
        )

        messages.success(request, f"Mot de passe réinitialisé pour {user_obj.username}.")
        return redirect('manage_users')

    return render(request, 'core/admin/reset_password.html', {
        'user_obj': user_obj,
        'title': 'Réinitialiser mot de passe'
    })



@role_required(['superadmin', 'organisateur'])
def reset_team_user_password(request, team_id):
    team = get_object_or_404(Team, pk=team_id)

    if not team.user:
        messages.error(request, "Cette équipe n'a aucun compte utilisateur lié.")
        return redirect('team_list')

    user_obj = team.user

    if request.method == 'POST':
        new_password = (request.POST.get('new_password') or '').strip()

        if len(new_password) < 4:
            messages.error(request, "Mot de passe trop court (minimum 4 caractères).")
            return redirect('reset_team_user_password', team_id=team_id)

        user_obj.set_password(new_password)
        user_obj.save()

        AdminLog.objects.create(
            user=request.user,
            action=f"Reset mot de passe pour {user_obj.username} (team {team.abbreviation})"
        )

        messages.success(request, f"Mot de passe réinitialisé pour {user_obj.username}.")
        return redirect('team_list')

    return render(request, 'core/admin/reset_password_team.html', {
        'team': team,
        'user_obj': user_obj,
        'title': 'Réinitialiser mot de passe'
    })


from .models import LeagueDrawSession, LeagueDrawPair

def _order_pair(team1, team2):
    return (team1, team2) if team1.id < team2.id else (team2, team1)

def _degree(session, team):
    return LeagueDrawPair.objects.filter(session=session).filter(
        Q(team_a=team) | Q(team_b=team)
    ).count()



@role_required(['superadmin', 'organisateur'])
def league_draw_live(request):
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(is_active=True, competition=competition).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    # Teams validées
    teams = Team.objects.filter(payment_validated=True, competition=competition).annotate(
        draw_count=Count('league_pairs_a', filter=Q(league_pairs_a__session=session), distinct=True) +
                   Count('league_pairs_b', filter=Q(league_pairs_b__session=session), distinct=True)
    ).order_by('team_name')

    pairs_qs = LeagueDrawPair.objects.filter(session=session).select_related('team_a', 'team_b')
    pairs_count = pairs_qs.count()

    teams_count = teams.count()
    done = (teams_count > 0 and all(t.draw_count >= 8 for t in teams))

    last_pairs = pairs_qs.order_by('-created_at')[:50]

    return render(request, 'core/admin/league_draw_live.html', {
        'competition': competition,
        'session': session,
        'teams': teams,
        'pairs': last_pairs,
        'done': done,
        'teams_count': teams_count,
        'pairs_count': pairs_count,
    })

@role_required(['superadmin', 'organisateur'])
def league_draw_random8(request, team_id):
    competition = Competition.objects.filter(is_active=True).first()
    session = LeagueDrawSession.objects.filter(is_active=True, competition=competition).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    team = get_object_or_404(Team, pk=team_id, payment_validated=True, competition=competition)

    with transaction.atomic():
        # Tant que l'équipe n'a pas 8 adversaires
        safety = 0
        while _degree(session, team) < 8:
            safety += 1
            if safety > 2000:
                messages.error(request, "Blocage détecté (safety stop). Utilise Reset et relance.")
                return redirect('league_draw_live')

            # équipes déjà rencontrées par team
            existing = LeagueDrawPair.objects.filter(session=session).filter(
                Q(team_a=team) | Q(team_b=team)
            )
            already_ids = set()
            for p in existing:
                already_ids.add(p.team_a_id)
                already_ids.add(p.team_b_id)
            already_ids.discard(team.id)

            # candidats: validés, même compétition, pas lui, pas déjà rencontrés, et avec slots dispo (<8)
            candidates = Team.objects.filter(payment_validated=True, competition=competition).exclude(pk=team.id).exclude(pk__in=already_ids)

            candidates = [t for t in candidates if _degree(session, t) < 8]

            if not candidates:
                messages.error(request, "Impossible de compléter les 8 adversaires (plus de candidats). Reset recommandé.")
                return redirect('league_draw_live')

            opponent = random.choice(list(candidates))
            a, b = _order_pair(team, opponent)
            LeagueDrawPair.objects.get_or_create(session=session, team_a=a, team_b=b)

    messages.success(request, f"Tirage terminé: {team.team_name} a maintenant 8 adversaires.")
    return redirect('league_draw_live')


@role_required(['superadmin', 'organisateur'])
def league_draw_reset(request):
    competition = Competition.objects.filter(is_active=True).first()
    session = LeagueDrawSession.objects.filter(is_active=True, competition=competition).order_by('-created_at').first()
    if session:
        session.pairs.all().delete()
    messages.warning(request, "Tirage réinitialisé.")
    return redirect('league_draw_live')


@role_required(['superadmin', 'organisateur'])
def league_draw_generate_matches(request):
    """
    Crée Phase 'league' + Matchs à partir des paires.
    - Home/Away fixe: team_a (home) vs team_b (away)
    - Date de départ choisie via formulaire (jour), heure auto 00:00
    - scheduled_date: placeholders toutes les 10 minutes (tu modifies ensuite)
    - Anti-doublons: vérifie aussi l'inverse
    """
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(is_active=True, competition=competition).order_by('-created_at').first()
    if not session:
        messages.error(request, "Aucun tirage actif.")
        return redirect('league_draw_live')

    teams = Team.objects.filter(payment_validated=True, competition=competition)

    # Vérifier tirage complet (8 adversaires par équipe)
    degs = {t.id: _degree(session, t) for t in teams}
    not_ready = [t for t in teams if degs.get(t.id, 0) < 8]
    if not_ready:
        messages.error(request, "Tirage incomplet: certaines équipes n'ont pas 8 adversaires.")
        return redirect('league_draw_live')

    pairs_qs = LeagueDrawPair.objects.filter(session=session).select_related('team_a', 'team_b').order_by('id')
    pairs_count = pairs_qs.count()
    if pairs_count != 144:
        messages.warning(request, f"Attention: nombre de paires = {pairs_count} (attendu: 144 pour 36 équipes).")

    # GET -> afficher formulaire
    if request.method != 'POST':
        return render(request, 'core/admin/league_generate_matches.html', {
            'competition': competition,
            'pairs_count': pairs_count
        })

    # POST -> générer
    start_date_str = (request.POST.get('start_date') or '').strip()
    if not start_date_str:
        messages.error(request, "Veuillez choisir une date de début.")
        return redirect('league_draw_generate_matches')

    try:
        # attendu: YYYY-MM-DD
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Format de date invalide. Utilise YYYY-MM-DD.")
        return redirect('league_draw_generate_matches')

    # base datetime à 00:00 heure locale
    base_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    slot_minutes = 10

    # Phase league (création si inexistante)
    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name='league',
        defaults={'order': 1, 'is_active': True}
    )

    created = 0
    existing = 0

    with transaction.atomic():
        for i, p in enumerate(pairs_qs):
            home = p.team_a
            away = p.team_b
            scheduled = base_dt + timedelta(minutes=slot_minutes * i)

            # Anti-doublons (même paire, peu importe le sens)
            pair_exists = Match.objects.filter(phase=phase).filter(
                Q(home_team=home, away_team=away) | Q(home_team=away, away_team=home)
            ).exists()

            if pair_exists:
                existing += 1
                continue

            Match.objects.create(
                phase=phase,
                home_team=home,
                away_team=away,
                match_leg='unique',
                scheduled_date=scheduled,
                is_played=False
            )
            created += 1

    messages.success(request, f"Phase League OK. Matchs générés: {created} créés, {existing} déjà existants.")
    return redirect('dashboard')


@role_required(['superadmin', 'organisateur'])
def league_draw_global(request):
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    session = LeagueDrawSession.objects.filter(is_active=True, competition=competition).order_by('-created_at').first()
    if not session:
        session = LeagueDrawSession.objects.create(
            name=f"Tirage Ligue - {competition.name}",
            competition=competition,
            is_active=True
        )

    teams = list(Team.objects.filter(payment_validated=True, competition=competition).order_by('id'))

    if len(teams) != 36:
        messages.error(request, f"Tirage global nécessite 36 équipes validées. Actuel: {len(teams)}.")
        return redirect('league_draw_live')

    # RESET + MESSAGE
    deleted = session.pairs.count()
    if deleted > 0:
        session.pairs.all().delete()
        messages.warning(request, f"Tirage existant supprimé: {deleted} paires effacées. Nouveau tirage global en cours...")

    # Randomiser l'ordre des équipes (effet tirage)
    random.shuffle(teams)

    n = len(teams)
    k = 4  # 4 voisins devant => degré 8 total

    created = 0
    with transaction.atomic():
        for i in range(n):
            for d in range(1, k + 1):
                t1 = teams[i]
                t2 = teams[(i + d) % n]  # uniquement vers l'avant => pas de doublons
                a, b = _order_pair(t1, t2)
                obj, was_created = LeagueDrawPair.objects.get_or_create(session=session, team_a=a, team_b=b)
                if was_created:
                    created += 1

    messages.success(request, f"Tirage global terminé: {created} paires créées (attendu: 144).")
    return redirect('league_draw_live')

@role_required(['superadmin', 'organisateur'])
def league_generate_8_matchdays(request):
    """
    Génère Phase 'league' + 8 journées.
    - 36 équipes validées uniquement
    - 18 matchs / journée
    - 2 journées / jour => 4 jours au total
    - Journée impaire => 00:00, Journée paire => 00:01 (même fenêtre 24h)
    - Les joueurs peuvent jouer n'importe quelle heure dans la journée (00:00-23:59)

    MODE A (DELETE) :
    - Supprime d'abord tous les Matchs existants de la phase 'league' (pour repartir propre).
    """
    competition = Competition.objects.filter(is_active=True).first()
    if not competition:
        messages.error(request, "Aucune compétition active.")
        return redirect('dashboard')

    teams = list(Team.objects.filter(payment_validated=True, competition=competition).order_by('id'))
    if len(teams) != 36:
        messages.error(request, f"Cette génération nécessite 36 équipes validées. Actuel: {len(teams)}.")
        return redirect('league_draw_live')

    if request.method != 'POST':
        return render(request, 'core/admin/league_generate_8_matchdays.html', {
            'competition': competition
        })

    start_date_str = (request.POST.get('start_date') or '').strip()
    if not start_date_str:
        messages.error(request, "Veuillez choisir une date de début.")
        return redirect('league_generate_8_matchdays')

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    except ValueError:
        messages.error(request, "Format de date invalide.")
        return redirect('league_generate_8_matchdays')

    # Phase league
    phase, _ = Phase.objects.get_or_create(
        competition=competition,
        name='league',
        defaults={'order': 1, 'is_active': True}
    )

    # ✅ MODE A: on repart propre (supprime tous les matchs de league existants)
    deleted, _ = Match.objects.filter(phase=phase).delete()

    # Tirage aléatoire UEFA-style (round-robin partiel)
    random.shuffle(teams)

    fixed = teams[0]
    rotating = teams[1:]  # 35
    n_rounds = 8          # 8 journées

    created = 0

    with transaction.atomic():
        for r in range(1, n_rounds + 1):
            left = [fixed] + rotating[:17]      # 18
            right = rotating[17:][::-1]         # 18 (inversée)
            day_pairs = list(zip(left, right))  # 18 matchs

            # 2 journées par jour (même fenêtre 24h)
            day_index = (r - 1) // 2
            minute = 0 if (r % 2 == 1) else 1   # 00:00 et 00:01

            round_dt = timezone.make_aware(
                datetime.combine(start_date + timedelta(days=day_index), datetime.min.time())
            ).replace(hour=0, minute=minute, second=0, microsecond=0)

            for t1, t2 in day_pairs:
                # Home/Away fixe et stable (ordre par id pour éviter doublons)
                home, away = _order_pair(t1, t2)

                Match.objects.create(
                    phase=phase,
                    home_team=home,
                    away_team=away,
                    match_leg='unique',
                    scheduled_date=round_dt,
                    matchday=r,
                    is_played=False
                )
                created += 1

            # Rotation cercle
            rotating = [rotating[-1]] + rotating[:-1]

    messages.success(
        request,
        f"Calendrier League généré: {created} matchs créés (8 journées). "
        f"Ancien calendrier supprimé: {deleted} matchs."
    )
    return redirect('dashboard')