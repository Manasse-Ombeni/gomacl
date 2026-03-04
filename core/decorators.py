# core/decorators.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from functools import wraps

def role_required(allowed_roles):
    """
    Décorateur pour restreindre l'accès selon le rôle dans UserProfile
    allowed_roles = liste ou string (ex: ['superadmin', 'organisateur'] ou 'superadmin')
    """
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not hasattr(request.user, 'userprofile'):
                return redirect('home')

            if request.user.userprofile.role not in allowed_roles:
                return redirect('dashboard')  # ou 'home' si tu veux

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator