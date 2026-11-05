import random
import string

from django.db import migrations, models


def backfill_codes(apps, schema_editor):
    Candidate = apps.get_model("candidates", "Candidate")
    used = set()
    for candidate in Candidate.objects.all():
        while True:
            code = "".join(random.choice(string.ascii_uppercase) + random.choice(string.digits) for _ in range(3))
            if code not in used:
                used.add(code)
                break
        candidate.code = code
        candidate.save(update_fields=["code"])


class Migration(migrations.Migration):
    dependencies = [("candidates", "0001_initial")]

    operations = [
        migrations.AlterModelOptions(name="candidate", options={"ordering": ["-created_at", "-id"]}),
        migrations.AddField(model_name="candidate", name="code", field=models.CharField(max_length=6, null=True, editable=False)),
        migrations.RunPython(backfill_codes, migrations.RunPython.noop),
        migrations.AlterField(model_name="candidate", name="code", field=models.CharField(max_length=6, unique=True, editable=False)),
    ]
