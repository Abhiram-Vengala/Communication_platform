from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from candidates.models import Candidate

from . import templating
from .models import Message, MessageBatch, MessageTemplate, StatusEvent


class CandidateBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = ["id", "code", "name", "phone", "email"]


class MessageSerializer(serializers.ModelSerializer):
    candidate = CandidateBriefSerializer(read_only=True)
    batch_id = serializers.IntegerField(read_only=True)
    last_error = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "candidate", "batch_id", "body", "provider", "status",
            "failure_code", "failure_message", "retryable", "last_error",
            "attempts", "next_attempt_at", "scheduled_for",
            "created_at", "sent_at", "delivered_at", "read_at",
        ]  # fmt: skip

    def get_last_error(self, obj):
        """Set while a temporary failure is being retried automatically."""
        return obj.failure_message if obj.status == Message.Status.QUEUED and obj.failure_message else ""


class StatusEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusEvent
        fields = ["status", "occurred_at", "applied"]


class MessageDetailSerializer(MessageSerializer):
    events = StatusEventSerializer(many=True, read_only=True)

    class Meta(MessageSerializer.Meta):
        fields = MessageSerializer.Meta.fields + ["events"]


class BatchSerializer(serializers.ModelSerializer):
    messages = MessageSerializer(many=True, read_only=True)
    summary = serializers.SerializerMethodField()

    class Meta:
        model = MessageBatch
        fields = ["id", "body", "provider", "created_at", "summary", "messages"]

    def get_summary(self, obj):
        statuses = [m.status for m in obj.messages.all()]
        by_status = {}
        for s in statuses:
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": len(statuses),
            "pending": sum(s in Message.PENDING for s in statuses),
            "succeeded": sum(s in Message.ACCEPTED for s in statuses),
            "failed": sum(s == Message.Status.FAILED for s in statuses),
            "by_status": by_status,
        }


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ["id", "name", "body", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_body(self, value):
        try:
            templating.check_placeholders(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value


class _SendBase(serializers.Serializer):
    body = serializers.CharField(required=False, max_length=1600)
    template_id = serializers.PrimaryKeyRelatedField(
        queryset=MessageTemplate.objects.all(), required=False, error_messages={"does_not_exist": "Template not found."}
    )
    provider = serializers.ChoiceField(choices=list(settings.PROVIDERS), default=settings.DEFAULT_PROVIDER)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)

    def validate_scheduled_for(self, value):
        if value and value <= timezone.now():
            raise serializers.ValidationError("Pick a time in the future.")
        return value

    def validate(self, attrs):
        template = attrs.pop("template_id", None)
        body = attrs.get("body") or (template.body if template else None)
        if not body:
            raise serializers.ValidationError({"body": "Write a message or pick a template."})
        try:
            templating.check_placeholders(body)
        except ValueError as exc:
            raise serializers.ValidationError({"body": str(exc)})
        attrs["body"] = body
        return attrs


class SendMessageSerializer(_SendBase):
    candidate_id = serializers.PrimaryKeyRelatedField(
        queryset=Candidate.objects.all(), error_messages={"does_not_exist": "Candidate not found."}
    )


class BulkSendSerializer(_SendBase):
    candidate_ids = serializers.PrimaryKeyRelatedField(
        queryset=Candidate.objects.all(),
        many=True,
        allow_empty=False,
        error_messages={"does_not_exist": "Candidate {pk_value} not found.", "empty": "Select at least one candidate."},
    )

    def validate_candidate_ids(self, value):
        unique = list({c.pk: c for c in value}.values())
        if len(unique) > settings.MAX_BULK_RECIPIENTS:
            raise serializers.ValidationError(f"You can message up to {settings.MAX_BULK_RECIPIENTS} candidates at once.")
        return unique
