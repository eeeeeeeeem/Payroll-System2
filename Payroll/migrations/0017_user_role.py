# Generated by Django 5.1.2 on 2024-11-22 11:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Payroll', '0016_user_is_active_user_is_staff'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('HR', 'Human Resources'), ('EMPLOYEE', 'Employee')], default='EMPLOYEE', max_length=20),
        ),
    ]
