"""Session helpers for the Ruckus Unleashed integration."""

from __future__ import annotations

import ssl

import aiohttp

from .const import CONF_VERIFY_SSL


def create_client_session(verify_ssl: bool) -> aiohttp.ClientSession:
    """Create an aiohttp ClientSession for use with aioruckus.

    We deliberately create our own session rather than reusing the HA shared
    session: aioruckus mutates ``websession.headers`` (setting a CSRF token)
    which must not leak into HA's global session. When ``verify_ssl`` is False
    we relax the SSL context so self-signed Ruckus certificates are accepted,
    mirroring aioruckus' own ``create_legacy_client_session``.
    """
    if verify_ssl:
        return aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            cookie_jar=aiohttp.CookieJar(unsafe=True),
        )

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    ssl_context.set_ciphers("DEFAULT")

    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10),
        cookie_jar=aiohttp.CookieJar(unsafe=True),
        connector=aiohttp.TCPConnector(keepalive_timeout=5, ssl=ssl_context),
    )


def verify_ssl_from_data(data: dict) -> bool:
    """Read the verify_ssl flag from a config entry, defaulting to True."""
    return data.get(CONF_VERIFY_SSL, True)
