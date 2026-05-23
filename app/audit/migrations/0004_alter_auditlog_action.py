# Generated for member admin actions (password reset, MFA removal).

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0003_alter_auditlog_action"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("member.create", "Member created"),
                    ("member.update", "Member updated"),
                    ("member.activate", "Member activated"),
                    ("member.deactivate", "Member deactivated"),
                    ("member.password_reset", "Password reset email sent"),
                    ("member.mfa_remove", "MFA device removed"),
                    ("group.add_member", "Added to group"),
                    ("group.remove_member", "Removed from group"),
                    ("import.create", "Import created"),
                    ("import.run", "Import run"),
                    ("settings.update", "Settings updated"),
                ],
                max_length=64,
                verbose_name="action",
            ),
        ),
    ]
