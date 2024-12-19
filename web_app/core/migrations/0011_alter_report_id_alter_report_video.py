# Generated by Django 5.0 on 2024-12-17 16:44

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_report'),
    ]

    operations = [
        migrations.AlterField(
            model_name='report',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='report',
            name='video',
            field=models.FileField(blank=True, null=True, upload_to='reports/videos/'),
        ),
    ]
