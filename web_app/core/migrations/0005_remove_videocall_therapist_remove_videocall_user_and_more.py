# Generated by Django 5.0 on 2024-12-17 00:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_remove_aicompanion_avatar_base_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='videocall',
            name='therapist',
        ),
        migrations.RemoveField(
            model_name='videocall',
            name='user',
        ),
        migrations.DeleteModel(
            name='Therapist',
        ),
        migrations.DeleteModel(
            name='VideoCall',
        ),
    ]
