import json

from django.conf import settings
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import AttemptCounter, Message, ServiceState
from .scenarios import FLAKY_FAILURES, is_valid_recipient, scenario_for
from .webhooks import start_lifecycle

CHANNELS = {"whatsapp", "email"}


def error(status, code, message, headers=None):
    resp = JsonResponse({"error": {"code": code, "message": message}}, status=status)
    for key, value in (headers or {}).items():
        resp[key] = value
    return resp


def serialize(msg):
    return {
        "id": msg.id,
        "status": msg.status,
        "channel": msg.channel,
        "to": msg.to,
        "error_code": msg.error_code or None,
        "created_at": msg.created_at.isoformat(),
    }


def authorized(request):
    return request.headers.get("Authorization") == f"Bearer {settings.API_KEY}"


@csrf_exempt
def messages(request):
    if request.method != "POST":
        return error(405, "method_not_allowed", "Use POST.")
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")

    state = ServiceState.load()
    if state.mode == "outage":
        return error(503, "service_unavailable", "The service is down for maintenance.")
    if state.mode == "rate_limit":
        return error(429, "rate_limited", "Too many requests.", {"Retry-After": "3"})

    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return error(400, "invalid_request", "Body must be valid JSON.")
    to, body, channel = data.get("to"), data.get("body"), data.get("channel", "whatsapp")
    if not isinstance(to, str) or not isinstance(body, str) or not body.strip():
        return error(400, "invalid_request", "'to' and a non-empty 'body' are required.")
    if channel not in CHANNELS:
        return error(400, "invalid_request", f"Unsupported channel '{channel}'.")
    if not is_valid_recipient(channel, to):
        return error(400, "invalid_recipient", "The recipient address is not valid.")

    key = request.headers.get("Idempotency-Key") or None
    if key:
        existing = Message.objects.filter(idempotency_key=key).first()
        if existing:
            resp = JsonResponse(serialize(existing), status=200)
            resp["Idempotent-Replay"] = "true"
            return resp

    scenario = scenario_for(to)
    if scenario == "invalid":
        return error(400, "invalid_recipient", "This recipient is not reachable on this channel.")
    if scenario == "ratelimit":
        return error(429, "rate_limited", "Too many requests.", {"Retry-After": "3"})
    if scenario == "flaky" and AttemptCounter.bump(key or to) <= FLAKY_FAILURES:
        return error(503, "service_unavailable", "Temporary upstream failure.")

    msg = Message.objects.create(channel=channel, to=to, body=body, scenario=scenario, idempotency_key=key)
    start_lifecycle(msg.id)
    return JsonResponse(serialize(msg), status=202)


def message_detail(request, message_id):
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")
    msg = Message.objects.filter(pk=message_id).first()
    if not msg:
        return error(404, "not_found", "Message not found.")
    return JsonResponse(serialize(msg))


def health(request):
    state = ServiceState.load()
    status = {"normal": "operational", "rate_limit": "degraded", "outage": "down"}[state.mode]
    counts = dict(Message.objects.values_list("status").annotate(n=Count("id")))
    return JsonResponse({"status": status, "mode": state.mode, "stats": counts})


@csrf_exempt
def admin_state(request):
    """Flip simulated behaviour for demos: {"mode": "outage", "duplicate_webhooks": true}."""
    if not authorized(request):
        return error(401, "unauthorized", "Missing or invalid API key.")
    state = ServiceState.load()
    if request.method == "POST":
        try:
            data = json.loads(request.body or b"{}")
        except ValueError:
            return error(400, "invalid_request", "Body must be valid JSON.")
        mode = data.get("mode", state.mode)
        if mode not in dict(ServiceState.MODES):
            return error(400, "invalid_request", "mode must be normal, rate_limit or outage.")
        state.mode = mode
        state.duplicate_webhooks = bool(data.get("duplicate_webhooks", state.duplicate_webhooks))
        state.out_of_order = bool(data.get("out_of_order", state.out_of_order))
        state.save()
    return JsonResponse(
        {"mode": state.mode, "duplicate_webhooks": state.duplicate_webhooks, "out_of_order": state.out_of_order}
    )
