# Generated by Django 5.1.2 on 2024-11-07 03:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Payroll', '0005_alter_user_date_of_birth'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='employement_start',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='job_title_id',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
