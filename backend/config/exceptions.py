"""One error envelope for every failure:

    {"error": {"code": "validation_error", "message": "...", "fields": {...}}}

so the frontend can show `message` directly and map `fields` onto form inputs.
"""
import logging

from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"
    default_detail = "This action isn't allowed in the current state."


def _flatten(detail):
    if isinstance(detail, dict):
        return {k: _flatten(v) for k, v in detail.items()}
    if isinstance(detail, (list, tuple)):
        flat = [_flatten(d) for d in detail]
        return flat[0] if len(flat) == 1 and isinstance(flat[0], str) else flat
    return str(detail)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error", exc_info=exc)
        return Response(
            {"error": {"code": "server_error", "message": "Something went wrong on our side. Please try again."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, ValidationError):
        error = {
            "code": "validation_error",
            "message": "Some of the information you entered needs fixing.",
            "fields": _flatten(response.data),
        }
    else:
        error = {"code": getattr(exc, "default_code", "error"), "message": str(getattr(exc, "detail", exc))}
    response.data = {"error": error}
    return response
