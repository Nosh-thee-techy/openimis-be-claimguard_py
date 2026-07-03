# Add HistoryModel.version column missing from initial migration.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("claimguard", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="claimfraudscore",
            name="version",
            field=models.IntegerField(default=1),
        ),
        migrations.AddField(
            model_name="fraudauditlog",
            name="version",
            field=models.IntegerField(default=1),
        ),
    ]
