from django.urls import path
from . import views

urlpatterns = [
    # Pages publiques
    path('', views.home, name='home'),
    path('register/', views.register_team, name='register_team'),
    path('teams/', views.teams_list, name='teams_list'),
    path('standings/', views.standings, name='standings'),
    path('fixtures/', views.fixtures, name='fixtures'),
    path('results/', views.results, name='results'),
    path('bracket/', views.bracket, name='bracket'),
    path('rules/', views.rules, name='rules'),
    path('about/', views.about, name='about'),
    path('news/', views.news_list, name='news_list'),
    path('news/<int:pk>/', views.news_detail, name='news_detail'),
    path('dashboard/calendar-pdf/', views.download_calendar_pdf, name='download_calendar_pdf'),
    
    # Authentification
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    path('my-matches/', views.my_matches, name='my_matches'),
    path('report-match/<int:match_id>/', views.report_match, name='report_match'),
   
    
    # Validation des paiements
    path('dashboard/pending-payments/', views.pending_payments, name='pending_payments'),
    path('dashboard/validate-payment/<int:team_id>/', views.validate_payment, name='validate_payment'),
    
    # Admin
    path('dashboard/', views.dashboard, name='dashboard'),
    path('encode-result/<int:match_id>/', views.encode_result, name='encode_result'),
    path('dashboard/generate-calendar/', views.generate_calendar, name='generate_calendar'),
    path('dashboard/check-forfeits/', views.check_forfeits_view, name='check_forfeits_view'),
    path('dashboard/generate-playoffs/', views.generate_playoffs_view, name='generate_playoffs_view'),
    path('dashboard/reset-competition/', views.reset_competition_view, name='reset_competition_view'),
    path('dashboard/reported-matches/', views.reported_matches, name='reported_matches'),
    path('dashboard/apply-forfeit/<int:match_id>/', views.apply_forfeit_manual, name='apply_forfeit_manual'),
]



    
    # Admin - Matchs signalés
    


