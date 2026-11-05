from django.contrib import admin

from .models import Message, MessageBatch, MessageTemplate, StatusEvent

for model in (Message, MessageBatch, MessageTemplate, StatusEvent):
    admin.site.register(model)
