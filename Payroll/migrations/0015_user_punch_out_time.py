# Generated by Django 5.1.2 on 2024-11-22 09:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Payroll', '0014_department_alter_salarypayment_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='punch_out_time',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
