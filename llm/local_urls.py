"""Validation of user-supplied local server URLs (Ollama, LM Studio, llama.cpp).

The server fetches these URLs on the user's behalf ("Refresh models", "Test
connection"), so on an instance shared by several users an unrestricted URL
would let anyone probe the internal network (the database, other containers,
cloud metadata). The rules:

* only ``http``/``https``, a hostname, an optional valid port, and a path — no
  credentials, query string or fragment;
* the host must be in ``settings.ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS``, which the
  person running the server controls (``*`` allows any host);
* link-local, multicast, unspecified and reserved addresses are always refused,
  even with ``*`` and after DNS resolution — 169.254.169.254 is the cloud
  metadata endpoint, never a model server.
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

from django.conf import settings
from django.utils.translation import gettext as _


class LocalURLError(ValueError):
    """A local server URL that must not be used; ``args[0]`` is a user-facing message."""


def allowed_hosts() -> list[str]:
    """Hosts local server URLs may point to (lower-case; ``*`` means any)."""
    configured = getattr(settings, 'ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS', None) or []
    return [h.strip().lower().rstrip('.') for h in configured if h.strip()]


def _forbidden_ip(ip: ipaddress._BaseAddress) -> bool:
    if ip.is_loopback:
        return False  # where local model servers live (note: ::1 also counts as "reserved")
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or ip.is_reserved


def _resolves_to_forbidden_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError, OSError):
        return False  # unresolvable: the request itself will fail with a clear message
    for info in infos:
        try:
            if _forbidden_ip(ipaddress.ip_address(info[4][0].split('%')[0])):
                return True
        except ValueError:
            continue
    return False


def validate_local_url(url: str) -> str:
    """Return ``url`` normalized (no trailing slash) or raise :class:`LocalURLError`."""
    url = (url or '').strip()
    try:
        parts = urlsplit(url)
        port = parts.port  # raises ValueError for an invalid port
    except ValueError as exc:
        raise LocalURLError(_('Enter a valid server URL, such as http://localhost:11434.')) from exc

    if parts.scheme not in ('http', 'https') or not parts.hostname:
        raise LocalURLError(_('Enter a URL starting with http:// or https://.'))
    if parts.username or parts.password:
        raise LocalURLError(_("Don't put a username or password in the server URL."))
    if parts.query or parts.fragment:
        raise LocalURLError(_('The server URL cannot have a query string or fragment.'))
    if port == 0:
        raise LocalURLError(_('Enter a valid server URL, such as http://localhost:11434.'))

    host = parts.hostname.lower().rstrip('.')
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and _forbidden_ip(literal):
        raise LocalURLError(_('This address cannot be used for a model server.'))

    hosts = allowed_hosts()
    if '*' not in hosts:
        if host not in hosts:
            raise LocalURLError(_(
                'This server is not on the list of allowed hosts (%(hosts)s). Ask whoever runs '
                'Ascendia to add it to ASCENDIA_LOCAL_LLM_ALLOWED_HOSTS.'
            ) % {'hosts': ', '.join(hosts) or '—'})
    elif literal is None and _resolves_to_forbidden_ip(host):
        raise LocalURLError(_('This address cannot be used for a model server.'))

    return url.rstrip('/')
