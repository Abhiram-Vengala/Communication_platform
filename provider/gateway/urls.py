from django.urls import path

from . import views

urlpatterns = [
    path("v1/messages", views.messages),
    path("v1/messages/<str:message_id>", views.message_detail),
    path("v1/health", views.health),
    path("v1/admin/state", views.admin_state),
]
