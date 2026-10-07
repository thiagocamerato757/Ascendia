"""Cache-busted static URLs.

``{% asset 'css/tokens.css' %}`` renders ``/static/css/tokens.css?v=<hash>``,
where the hash comes from the file's content. Without it the browser keeps
serving a stale stylesheet after a change, because the static URL never moves
(see docs/decisions.md). Under DEBUG the hash is recomputed on every render so
edits show up immediately; otherwise it is computed once per process.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

from django import template
from django.conf import settings
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


def _digest(path: str) -> str:
    found = finders.find(path)
    if not found:
        return ''
    with open(found, 'rb') as fh:
        return hashlib.md5(fh.read(), usedforsecurity=False).hexdigest()[:12]


_cached_digest = lru_cache(maxsize=None)(_digest)


@register.simple_tag
def asset(path: str) -> str:
    """Static URL for ``path`` with a content-hash query string."""
    digest = _digest(path) if settings.DEBUG else _cached_digest(path)
    url = static(path)
    return f'{url}?v={digest}' if digest else url
