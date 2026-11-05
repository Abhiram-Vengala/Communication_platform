import re

from django.db.models import OuterRef, Q, Subquery
from django.utils.dateparse import parse_date
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from messaging.models import Message

from .models import Candidate
from .serializers import CandidateSerializer

ORDERINGS = {
    "name": "name", "-name": "-name",
    "created_at": "created_at", "-created_at": "-created_at",
    "last_message_at": "last_message_at", "-last_message_at": "-last_message_at",
}  # fmt: skip
MAX_BULK_DELETE = 500


def _date_param(params, key):
    raw = params.get(key)
    if not raw:
        return None
    parsed = parse_date(raw)
    if parsed is None:
        raise serializers.ValidationError({key: "Use the format YYYY-MM-DD."})
    return parsed


class CandidateViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Candidates with their latest message status.

    List filters: ?search= (name, email, phone, ID), ?name= ?phone= ?code=,
    ?status=read,failed,none ("none" = never messaged), ?last_message_from= ?last_message_to= (YYYY-MM-DD),
    ?ordering=name|-created_at|-last_message_at (default newest first).
    """

    serializer_class = CandidateSerializer

    def get_queryset(self):
        latest = Message.objects.filter(candidate=OuterRef("pk")).order_by("-created_at", "-id")
        qs = Candidate.objects.annotate(
            last_message_at=Subquery(latest.values("created_at")[:1]),
            last_message_status=Subquery(latest.values("status")[:1]),
        )
        if self.action != "list":
            return qs

        p = self.request.query_params
        term = (p.get("search") or "").strip()
        if term:
            digits = re.sub(r"[\s\-().]", "", term)
            query = Q(name__icontains=term) | Q(email__icontains=term) | Q(code__icontains=term)
            if digits:
                query |= Q(phone__icontains=digits)
            qs = qs.filter(query)
        if p.get("name", "").strip():
            qs = qs.filter(name__icontains=p["name"].strip())
        if p.get("phone", "").strip():
            qs = qs.filter(phone__icontains=re.sub(r"[\s\-().]", "", p["phone"]))
        if p.get("code", "").strip():
            qs = qs.filter(code__icontains=p["code"].strip())

        if p.get("status"):
            wanted = [s.strip().lower() for s in p["status"].split(",") if s.strip()]
            allowed = {s.value for s in Message.Status} | {"none"}
            bad = [s for s in wanted if s not in allowed]
            if bad:
                raise serializers.ValidationError({"status": f"Unknown status: {', '.join(bad)}."})
            query = Q(last_message_status__in=[s for s in wanted if s != "none"])
            if "none" in wanted:
                query |= Q(last_message_status__isnull=True)
            qs = qs.filter(query)

        start, end = _date_param(p, "last_message_from"), _date_param(p, "last_message_to")
        if start:
            qs = qs.filter(last_message_at__date__gte=start)
        if end:
            qs = qs.filter(last_message_at__date__lte=end)

        ordering = ORDERINGS.get(p.get("ordering", ""), "-created_at")
        return qs.order_by(ordering, "-id")

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """Delete several candidates (and their message history) at once: {"ids": [1, 2]}."""
        ids = request.data.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) for i in ids):
            raise serializers.ValidationError({"ids": "Send a non-empty list of candidate ids."})
        if len(ids) > MAX_BULK_DELETE:
            raise serializers.ValidationError({"ids": f"You can delete up to {MAX_BULK_DELETE} candidates at once."})
        queryset = Candidate.objects.filter(pk__in=ids)
        deleted = queryset.count()
        queryset.delete()
        return Response({"deleted": deleted})
