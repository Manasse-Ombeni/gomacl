from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Team, Match, Competition

# ==========================================
# FORMULAIRE : INSCRIPTION D'UNE ÉQUIPE
# ==========================================
class TeamRegistrationForm(forms.ModelForm):
    # Champ pour le mot de passe
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 6 caractères'
        }),
        min_length=6,
        label=_('Mot de passe'),
        help_text=_('Ce mot de passe vous permettra de vous connecter pour voir vos matchs.')
    )
    
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmez le mot de passe'
        }),
        label=_('Confirmer le mot de passe')
    )
    
    class Meta:
        model = Team
        fields = ['player_name', 'team_name', 'abbreviation', 'whatsapp', 'logo', 'payment_proof']
        widgets = {
            'player_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: Manassé Ombeni'),
                'required': True
            }),
            'team_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: FC Barcelona, Real Madrid, etc.'),
                'required': True
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: BAR'),
                'maxlength': '3',
                'style': 'text-transform: uppercase;',
                'required': True
            }),
            'whatsapp': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _('Ex: +243999999999'),
                'required': True
            }),
            'logo': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'payment_proof': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'required': True
            }),
        }
        labels = {
            'player_name': _('Nom complet du joueur'),
            'team_name': _('Nom de votre équipe'),
            'abbreviation': _('Abréviation (3 lettres)'),
            'whatsapp': _('Numéro WhatsApp'),
            'logo': _('Logo de l\'équipe (optionnel)'),
            'payment_proof': _('Preuve de paiement (capture d\'écran)'),
        }
        help_texts = {
            'abbreviation': _('3 lettres majuscules (ex: BAR pour Barcelona)'),
            'whatsapp': _('Format international: +243999999999'),
            'payment_proof': _('Envoyez 1 000 CDF via Airtel Money au +243992848365, puis uploadez la capture d\'écran.'),
        }
    
    def clean_abbreviation(self):
        """Convertir l'abréviation en majuscules et vérifier l'unicité"""
        abbreviation = self.cleaned_data.get('abbreviation')
        if abbreviation:
            abbreviation = abbreviation.upper()
            
            if Team.objects.filter(abbreviation=abbreviation).exists():
                raise ValidationError(_('Cette abréviation est déjà utilisée. Veuillez en choisir une autre.'))
            
            if len(abbreviation) != 3:
                raise ValidationError(_('L\'abréviation doit contenir exactement 3 lettres.'))
            
            if not abbreviation.isalpha():
                raise ValidationError(_('L\'abréviation ne doit contenir que des lettres.'))
            
            return abbreviation
        return abbreviation
    
    def clean_whatsapp(self):
        """Valider le format du numéro WhatsApp"""
        whatsapp = self.cleaned_data.get('whatsapp')
        if whatsapp:
            whatsapp = whatsapp.replace(' ', '')
            
            if Team.objects.filter(whatsapp=whatsapp).exists():
                raise ValidationError(_('Ce numéro WhatsApp est déjà enregistré.'))
            
            return whatsapp
        return whatsapp
    
    def clean_password_confirm(self):
        """Vérifier que les deux mots de passe correspondent"""
        password = self.cleaned_data.get('password')
        password_confirm = self.cleaned_data.get('password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise ValidationError(_('Les mots de passe ne correspondent pas.'))
        
        return password_confirm
    
    def clean_logo(self):
        """Valider la taille de l'image du logo"""
        logo = self.cleaned_data.get('logo')
        if logo:
            if logo.size > 2 * 1024 * 1024:
                raise ValidationError(_('La taille du logo ne doit pas dépasser 2 MB.'))
            
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            ext = logo.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise ValidationError(_('Format non supporté. Utilisez JPG, PNG ou GIF.'))
            
            return logo
        return logo
    
    def clean_payment_proof(self):
        """Valider la preuve de paiement"""
        payment_proof = self.cleaned_data.get('payment_proof')
        if payment_proof:
            if payment_proof.size > 5 * 1024 * 1024:
                raise ValidationError(_('La taille de l\'image ne doit pas dépasser 5 MB.'))
            
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            ext = payment_proof.name.split('.')[-1].lower()
            if ext not in valid_extensions:
                raise ValidationError(_('Format non supporté. Utilisez JPG, PNG ou GIF.'))
            
            return payment_proof
        return payment_proof


# ==========================================
# FORMULAIRE : RÉSULTAT D'UN MATCH
# ==========================================
class MatchResultForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = [
            'home_score', 'away_score', 
            'home_extra_time', 'away_extra_time',
            'home_penalties', 'away_penalties',
            'is_forfeit', 'forfeit_team', 
            'screenshot', 'notes'
        ]
        widgets = {
            'home_score': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'min': '0',
                'max': '20',
                'placeholder': '0'
            }),
            'away_score': forms.NumberInput(attrs={
                'class': 'form-control form-control-lg',
                'min': '0',
                'max': '20',
                'placeholder': '0'
            }),
            'home_extra_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'placeholder': '0'
            }),
            'away_extra_time': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'placeholder': '0'
            }),
            'home_penalties': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'placeholder': '0'
            }),
            'away_penalties': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'placeholder': '0'
            }),
            'is_forfeit': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'forfeit_team': forms.Select(attrs={
                'class': 'form-select'
            }),
            'screenshot': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': _('Commentaires sur le match (optionnel)')
            }),
        }
        labels = {
            'home_score': _('Score équipe domicile (temps réglementaire)'),
            'away_score': _('Score équipe extérieur (temps réglementaire)'),
            'home_extra_time': _('Buts domicile (prolongation)'),
            'away_extra_time': _('Buts extérieur (prolongation)'),
            'home_penalties': _('Tirs au but domicile'),
            'away_penalties': _('Tirs au but extérieur'),
            'is_forfeit': _('Y a-t-il eu un forfait ?'),
            'forfeit_team': _('Équipe qui a fait forfait'),
            'screenshot': _('Capture d\'écran du résultat'),
            'notes': _('Notes / Commentaires'),
        }
        help_texts = {
            'home_extra_time': _('Laisser vide si pas de prolongation'),
            'away_extra_time': _('Laisser vide si pas de prolongation'),
            'home_penalties': _('Laisser vide si pas de tirs au but'),
            'away_penalties': _('Laisser vide si pas de tirs au but'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            self.fields['forfeit_team'].queryset = Team.objects.filter(
                pk__in=[self.instance.home_team.pk, self.instance.away_team.pk]
            )
            
            # Rendre les champs prolongation/TAB optionnels pour phase de ligue
            if self.instance.phase.name == 'league':
                self.fields['home_extra_time'].required = False
                self.fields['away_extra_time'].required = False
                self.fields['home_penalties'].required = False
                self.fields['away_penalties'].required = False
    
    def clean(self):
        """Validation croisée"""
        cleaned_data = super().clean()
        is_forfeit = cleaned_data.get('is_forfeit')
        forfeit_team = cleaned_data.get('forfeit_team')
        home_score = cleaned_data.get('home_score')
        away_score = cleaned_data.get('away_score')
        home_extra = cleaned_data.get('home_extra_time')
        away_extra = cleaned_data.get('away_extra_time')
        home_pen = cleaned_data.get('home_penalties')
        away_pen = cleaned_data.get('away_penalties')
        
        if is_forfeit:
            if not forfeit_team:
                raise ValidationError(_('Veuillez sélectionner l\'équipe qui a fait forfait.'))
            
            if forfeit_team == self.instance.home_team:
                cleaned_data['home_score'] = 0
                cleaned_data['away_score'] = 3
            else:
                cleaned_data['home_score'] = 3
                cleaned_data['away_score'] = 0
                
            # Pas de prolongation/TAB en cas de forfait
            cleaned_data['home_extra_time'] = None
            cleaned_data['away_extra_time'] = None
            cleaned_data['home_penalties'] = None
            cleaned_data['away_penalties'] = None
        else:
            if home_score is None or away_score is None:
                raise ValidationError(_('Veuillez entrer les scores des deux équipes.'))
            
            # Validation prolongation : les deux doivent être remplis ensemble
            if (home_extra is not None and away_extra is None) or (home_extra is None and away_extra is not None):
                raise ValidationError(_('Si vous entrez un score de prolongation, vous devez entrer les deux scores (domicile et extérieur).'))
            
            # Validation tirs au but : les deux doivent être remplis ensemble
            if (home_pen is not None and away_pen is None) or (home_pen is None and away_pen is not None):
                raise ValidationError(_('Si vous entrez des tirs au but, vous devez entrer les deux scores.'))
            
            # Les tirs au but ne peuvent pas être égaux
            if home_pen is not None and away_pen is not None and home_pen == away_pen:
                raise ValidationError(_('Les tirs au but ne peuvent pas être égaux. Il doit y avoir un vainqueur.'))
        
        return cleaned_data
    
    def clean_screenshot(self):
        """Valider la capture d'écran"""
        screenshot = self.cleaned_data.get('screenshot')
        if screenshot:
            if screenshot.size > 5 * 1024 * 1024:
                raise ValidationError(_('La taille de l\'image ne doit pas dépasser 5 MB.'))
            
            return screenshot
        return screenshot