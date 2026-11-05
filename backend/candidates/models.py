import random
import string

from django.db import models


def generate_code():
    """Short, readable public ID such as A1B2C3 (letter, digit, letter, digit...)."""
    return "".join(random.choice(string.ascii_uppercase) + random.choice(string.digits) for _ in range(3))


class Candidate(models.Model):
    code = models.CharField(max_length=6, unique=True, editable=False)
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16, unique=True)  # E.164
    email = models.EmailField(unique=True)  # stored lower-case
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def save(self, *args, **kwargs):
        if not self.code:
            for _ in range(20):
                code = generate_code()
                if not Candidate.objects.filter(code=code).exists():
                    self.code = code
                    break
            else:  # pragma: no cover
                raise RuntimeError("Could not generate a unique candidate code")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
