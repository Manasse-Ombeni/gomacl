from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Team, Match, Competition


# ==========================================
# FORMULAIRE : INSCRIPTION / MODIFICATION ÉQUIPE
# ==========================================
class TeamRegistrationForm(forms.ModelForm):

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=6,
        required=False,
        label=_('Mot de passe')
    )

    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        label=_('Confirmer le mot de passe')
    )

    class Meta:
        model = Team
        fields = ['player_name', 'team_name', 'abbreviation', 'whatsapp']

        widgets = {
            'player_name': forms.TextInput(attrs={'class': 'form-control'}),
            'team_name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control',
                'maxlength': '3',
                'style': 'text-transform: uppercase;',
            }),
            'whatsapp': forms.TextInput(attrs={'class': 'form-control'}),
        }

    # ✅ ABRÉVIATION UNIQUE CORRIGÉE
    def clean_abbreviation(self):
        abbreviation = self.cleaned_data.get('abbreviation')

        if abbreviation:
            abbreviation = abbreviation.upper()

            qs = Team.objects.filter(abbreviation=abbreviation)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(_('Cette abréviation est déjà utilisée.'))

            if len(abbreviation) != 3:
                raise ValidationError(_('L\'abréviation doit contenir exactement 3 lettres.'))

            if not abbreviation.isalpha():
                raise ValidationError(_('L\'abréviation doit contenir uniquement des lettres.'))

        return abbreviation

    # ✅ WHATSAPP UNIQUE CORRIGÉ
    def clean_whatsapp(self):
        whatsapp = self.cleaned_data.get('whatsapp')

        if whatsapp:
            whatsapp = whatsapp.replace(" ", "")

            qs = Team.objects.filter(whatsapp=whatsapp)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(_('Ce numéro WhatsApp est déjà enregistré.'))

        return whatsapp

    # ✅ GESTION PASSWORD INTELLIGENTE
    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        # ✅ SI CRÉATION → mot de passe obligatoire
        if not self.instance.pk:
            if not password:
                raise ValidationError(_('Le mot de passe est obligatoire.'))

            if password != password_confirm:
                raise ValidationError(_('Les mots de passe ne correspondent pas.'))

        # ✅ SI MODIFICATION → mot de passe facultatif
        else:
            if password:
                if password != password_confirm:
                    raise ValidationError(_('Les mots de passe ne correspondent pas.'))

        return cleaned_data

    # ✅ SAVE PASSWORD CORRECTEMENT
    def save(self, commit=True):
        team = super().save(commit=False)

        password = self.cleaned_data.get('password')

        # ✅ Vérifier si user existe
        if password and team.user:
            team.user.set_password(password)
            team.user.save()

        if commit:
            team.save()

        return team


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
            'notes'
        ]

        widgets = {
            'home_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'home_extra_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_extra_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'home_penalties': forms.NumberInput(attrs={'class': 'form-control'}),
            'away_penalties': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_forfeit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'forfeit_team': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()

        is_forfeit = cleaned_data.get('is_forfeit')
        home_score = cleaned_data.get('home_score')
        away_score = cleaned_data.get('away_score')
        home_pen = cleaned_data.get('home_penalties')
        away_pen = cleaned_data.get('away_penalties')

        if is_forfeit:
            return cleaned_data

        if home_score is None or away_score is None:
            raise ValidationError(_('Veuillez entrer les scores des deux équipes.'))

        if home_pen is not None and away_pen is not None:
            if home_pen == away_pen:
                raise ValidationError(_('Les tirs au but ne peuvent pas être égaux.'))

        return cleaned_data


# ==========================================
# FORMULAIRE : COMPÉTITION
# ==========================================
class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = [
            'name',
            'format_type',
            'max_teams',
            'registration_fee',
            'is_active',
            'registration_open',
            'start_date',
            'end_date'
        ]