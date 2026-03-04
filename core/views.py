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
from datetime import datetime
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
    latest_news = News.objects.filter(is_published=True)[:3]
    
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
            messages.error(request, _("Erreur dans le formulaire. Veuillez vérifier les informations."))
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
@role_required(['superadmin', 'paiement'])
def pending_payments(request):

    pending_teams = Team.objects.filter(
        payment_validated=False
    ).order_by('-created_at')

    return render(request, 'core/pending_payments.html', {
        'pending_teams': pending_teams,
    })


@role_required(['superadmin', 'paiement'])
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