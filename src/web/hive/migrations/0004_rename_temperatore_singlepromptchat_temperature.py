# Generated by Django 5.1.3 on 2024-12-05 17:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hive', '0003_singlepromptchat_max_tokens_singlepromptchat_model_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='singlepromptchat',
            old_name='temperatore',
            new_name='temperature',
        ),
    ]
