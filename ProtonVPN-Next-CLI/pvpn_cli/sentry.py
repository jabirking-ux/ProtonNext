import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import os

SENSITIVE_KEYS = {
    "AccessToken", "RefreshToken", "Password", "password",
    "ClientProof", "ClientEphemeral", "ServerEphemeral",
    "TwoFactorCode", "code", "wg_private_key"
}

SENSITIVE_HEADERS = {"Authorization", "x-pm-uid"}

def scrub_data(data):
    """Recursively redact sensitive keys from dictionaries/lists."""
    if isinstance(data, dict):
        return {
            k: ("[REDACTED]" if k in SENSITIVE_KEYS else scrub_data(v))
            for k, v in data.items()
        }
    elif isinstance(data, list):
        # Also limit huge lists like server lists
        if len(data) > 100:
            return ["[LIST_TOO_LARGE_REDACTED]"]
        return [scrub_data(item) for item in data]
    return data

# Exceptions that represent normal user/OS driven termination, not defects.
IGNORED_EXCEPTIONS = (KeyboardInterrupt, SystemExit, BrokenPipeError)

def before_send(event, hint):
    """Sentry hook to filter events before sending."""
    # Drop user-initiated interruptions (Ctrl+C, closed pipe, clean exit).
    # These were reported as errors CLI-8 / CLI-9 / CLI-A but are expected behaviour.
    exc_info = hint.get("exc_info") if hint else None
    if exc_info and isinstance(exc_info[1], IGNORED_EXCEPTIONS):
        return None

    # Scrub headers in request
    request = event.get("request")
    if request and "headers" in request:
        headers = request["headers"]
        for h in SENSITIVE_HEADERS:
            if h in headers:
                headers[h] = "[REDACTED]"
            # Case insensitive check for headers
            for k in list(headers.keys()):
                if k.lower() == h.lower():
                    headers[k] = "[REDACTED]"

    # Scrub extra data and breadcrumbs
    if "breadcrumbs" in event:
        for bc in event["breadcrumbs"].get("values", []):
            if "data" in bc:
                bc["data"] = scrub_data(bc["data"])

    # Scrub body if present
    if request and "data" in request:
        request["data"] = scrub_data(request["data"])

    return event

def init_sentry(dsn=None):
    # Tracking and telemetry completely disabled per privacy requirements
    return
