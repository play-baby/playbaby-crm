from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.conf import settings
from functools import wraps

LOGIN_ATTEMPTS_KEY = 'login_attempts_{}'
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

def login_rate_limit(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.method == 'POST':
            ip = request.META.get('REMOTE_ADDR', '')
            key = LOGIN_ATTEMPTS_KEY.format(ip)
            attempts = cache.get(key, 0)
            if attempts >= MAX_ATTEMPTS:
                return HttpResponseForbidden(
                    f'تم تجاوز الحد الأقصى لمحاولات تسجيل الدخول. '
                    f'يرجى المحاولة بعد {LOCKOUT_MINUTES} دقيقة.'
                )
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def record_failed_attempt(request):
    ip = request.META.get('REMOTE_ADDR', '')
    key = LOGIN_ATTEMPTS_KEY.format(ip)
    attempts = cache.get(key, 0)
    cache.set(key, attempts + 1, LOCKOUT_MINUTES * 60)

def clear_attempts(request):
    ip = request.META.get('REMOTE_ADDR', '')
    key = LOGIN_ATTEMPTS_KEY.format(ip)
    cache.delete(key)
