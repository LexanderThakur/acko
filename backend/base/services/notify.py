"""Webhook notifications (FR-10): fire-and-record POSTs to the receiver.

Deliberately non-fatal: a failing receiver must never fail a publishing
attempt — the Notification row records the delivery outcome instead.
"""
import json as jsonlib
import urllib.error
import urllib.request

from django.conf import settings

DEFAULT_TIMEOUT = 5


def send_webhook(payload, url=None, timeout=DEFAULT_TIMEOUT):
    """POST payload as JSON. Returns (delivered, response_status)."""
    url = url or settings.WEBHOOK_RECEIVER_URL
    data = jsonlib.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, response.status
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
        return False, None
