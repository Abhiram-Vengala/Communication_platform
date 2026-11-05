from rest_framework import serializers

from .models import Candidate
from .validators import normalize_phone


class CandidateSerializer(serializers.ModelSerializer):
    last_message_at = serializers.SerializerMethodField()
    last_message_status = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = ["id", "code", "name", "phone", "email", "created_at", "last_message_at", "last_message_status"]
        read_only_fields = ["id", "code", "created_at"]

    # Annotated by the list/detail queryset; None right after create (no messages yet).
    def get_last_message_at(self, obj):
        value = getattr(obj, "last_message_at", None)
        return value.isoformat().replace("+00:00", "Z") if value else None

    def get_last_message_status(self, obj):
        return getattr(obj, "last_message_status", None)

    def _others(self):
        qs = Candidate.objects.all()
        return qs.exclude(pk=self.instance.pk) if self.instance else qs

    def validate_name(self, value):
        value = " ".join(value.split())
        if len(value) < 2:
            raise serializers.ValidationError("Name must be at least 2 characters.")
        return value

    def validate_phone(self, value):
        try:
            phone = normalize_phone(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        if self._others().filter(phone=phone).exists():
            raise serializers.ValidationError("A candidate with this phone number already exists.")
        return phone

    def validate_email(self, value):
        email = value.strip().lower()
        if self._others().filter(email=email).exists():
            raise serializers.ValidationError("A candidate with this email already exists.")
        return email
