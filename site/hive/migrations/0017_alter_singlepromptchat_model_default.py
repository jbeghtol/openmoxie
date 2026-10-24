from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hive', '0016_globalresponse_source_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='singlepromptchat',
            name='model',
            field=models.CharField(default='gpt-6-luna', max_length=200),
        ),
    ]
