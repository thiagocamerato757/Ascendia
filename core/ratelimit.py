"""Per-user fixed-window rate limiting on the shared cache (spec §11).

The cache is Postgres-backed (``CACHES`` in settings), so every gunicorn worker
counts against the same window.
"""
from __future__ import annotations

import time
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

WINDOW_SECONDS = 60


def hit(scope: str, user_id: int, limit: int) -> bool:
    """Count one request; return False when ``limit`` per minute is exceeded."""
    if limit <= 0:
        return True
    window = int(time.time() // WINDOW_SECONDS)
    key = f'rl:{scope}:{user_id}:{window}'
    if cache.add(key, 1, timeout=WINDOW_SECONDS + 5):
        return True
    try:
        count = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.add(key, 1, timeout=WINDOW_SECONDS + 5)
        return True
    return count <= limit


def rate_limited(scope: str, setting_name: str):
    """View decorator: answer 429 with a short, translated message over the limit."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            limit = int(getattr(settings, setting_name, 0))
            if request.user.is_authenticated and not hit(scope, request.user.pk, limit):
                message = _('Too many requests. Wait a minute and try again.')
                if request.headers.get('HX-Request'):
                    # HTMX does not swap 4xx bodies by default: show the notice in place.
                    response = render(request, 'components/notice.html', {
                        'variant': 'warning', 'title': _('Slow down'), 'message': message,
                    })
                else:
                    response = HttpResponse(message, status=429, content_type='text/plain; charset=utf-8')
                response['Retry-After'] = str(WINDOW_SECONDS)
                return response
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
