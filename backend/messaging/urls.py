from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("messages", views.MessageViewSet, basename="message")
router.register("batches", views.BatchViewSet, basename="batch")
router.register("templates", views.TemplateViewSet, basename="template")

urlpatterns = [
    path("candidates/<int:candidate_id>/messages/", views.CandidateHistoryView.as_view()),
    path("webhooks/provider/", views.ProviderWebhookView.as_view()),
    path("provider-health/", views.ProviderHealthView.as_view()),
] + router.urls
