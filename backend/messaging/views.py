import hashlib
import hmac
import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from candidates.models import Candidate
from config.exceptions import Conflict

from . import services
from .models import Message, MessageBatch, MessageTemplate
from .providers import get_provider
from .serializers import (
    BatchSerializer,
    BulkSendSerializer,
    MessageDetailSerializer,
    MessageSerializer,
    SendMessageSerializer,
    TemplateSerializer,
)


class MessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List/filter (?status=failed,read &candidate= &batch=), send one, bulk send, retry."""

    def get_serializer_class(self):
        return MessageDetailSerializer if self.action == "retrieve" else MessageSerializer

    def get_queryset(self):
        qs = Message.objects.select_related("candidate")
        if self.action == "retrieve":
            qs = qs.prefetch_related("events")
        p = self.request.query_params
        if p.get("status"):
            qs = qs.filter(status__in=p["status"].split(","))
        if p.get("candidate"):
            qs = qs.filter(candidate_id=p["candidate"])
        if p.get("batch"):
            qs = qs.filter(batch_id=p["batch"])
        return qs

    def create(self, request):
        s = SendMessageSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        _, messages = services.create_messages(
            [d["candidate_id"]], d["body"], d["provider"], d.get("scheduled_for")
        )
        services.enqueue([m.id for m in messages])
        message = Message.objects.select_related("candidate").get(pk=messages[0].pk)
        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        s = BulkSendSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        batch, messages = services.create_messages(
            d["candidate_ids"], d["body"], d["provider"], d.get("scheduled_for"), batch_body=d["body"]
        )
        services.enqueue([m.id for m in messages])
        batch = MessageBatch.objects.prefetch_related("messages__candidate").get(pk=batch.pk)
        return Response(BatchSerializer(batch).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        message = self.get_object()
        try:
            services.retry_message(message)
        except services.NotRetryable as exc:
            raise Conflict(str(exc))
        services.enqueue([message.pk])
        message = Message.objects.select_related("candidate").get(pk=message.pk)
        return Response(MessageSerializer(message).data)


class BatchViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Poll this to watch a bulk send resolve, candidate by candidate."""

    serializer_class = BatchSerializer
    queryset = MessageBatch.objects.prefetch_related("messages__candidate")


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer
    queryset = MessageTemplate.objects.all()


class CandidateHistoryView(ListAPIView):
    """Full communication history for one candidate, newest first."""

    serializer_class = MessageSerializer

    def get_queryset(self):
        candidate = get_object_or_404(Candidate, pk=self.kwargs["candidate_id"])
        qs = candidate.messages.select_related("candidate")
        if self.request.query_params.get("status"):
            qs = qs.filter(status__in=self.request.query_params["status"].split(","))
        return qs


class ProviderWebhookView(APIView):
    """Receives signed status callbacks. Idempotent: replays return 200 and change nothing."""

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        expected = hmac.new(settings.PROVIDER_WEBHOOK_SECRET.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, request.headers.get("X-Signature", "")):
            return Response({"error": {"code": "invalid_signature", "message": "Bad signature."}}, status=401)
        try:
            payload = json.loads(request.body)
            result = services.apply_provider_event(payload)
        except ValueError:
            return Response({"error": {"code": "invalid_payload", "message": "Body must be JSON."}}, status=400)
        except services.InvalidEvent as exc:
            return Response({"error": {"code": "invalid_payload", "message": str(exc)}}, status=400)
        except services.UnknownMessage:
            # 404 makes the provider retry, which covers the callback racing our own DB write.
            return Response({"error": {"code": "unknown_message", "message": "Unknown message."}}, status=404)
        return Response({"result": result})


class ProviderHealthView(APIView):
    def get(self, request):
        providers = []
        for name, config in settings.PROVIDERS.items():
            health = get_provider(name).health()
            providers.append({"name": name, "label": config["label"], **health})
        states = {p["status"] for p in providers}
        overall = "down" if states == {"down"} else "operational" if states == {"operational"} else "degraded"
        return Response({"status": overall, "providers": providers, "stats": services.delivery_stats()})
