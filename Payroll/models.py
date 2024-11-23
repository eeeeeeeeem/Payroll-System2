import os

from django.utils.translation import gettext as _
from django.core.files.base import ContentFile
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from rest_framework.exceptions import ValidationError

from Payroll_System import settings


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, role='EMPLOYEE', **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class JobTitle(models.Model):
    job_title_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return self.title


class User(AbstractBaseUser):
    # Define role choices
    ROLE_CHOICES = (
        ('HR', 'Human Resources'),
        ('EMPLOYEE', 'Employee'),
    )

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    cityId = models.CharField(max_length=255)
    employement_start = models.DateField(null=True, blank=True)
    employement_end = models.DateField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    job_title = models.ForeignKey(JobTitle, on_delete=models.CASCADE, related_name='employees', default=1)
    punch_out_time = models.DateTimeField(null=True, blank=True)

    # Add role field
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='EMPLOYEE'
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'date_of_birth', 'gender', 'address', 'cityId', 'employement_start',
                       'job_title', 'employement_end']

    def is_hr(self):
        return self.role == 'HR'

    def is_employee(self):
        return self.role == 'EMPLOYEE'

    def has_hr_permission(self):
        return self.is_hr()

    def get_salary_slips(self):
        return SalaryPayment.objects.filter(user=self).order_by('-payment_date')

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def get_username(self):
        return self.email.split('@')[0]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class EmploymentTerms(models.Model):
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employment_terms")
    agreed_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_start_date = models.DateField()
    salary_end_date = models.DateField()

    class Meta:
        ordering = ['-salary_start_date']

    def __str__(self):
        return f"{self.employee.email} - {self.agreed_salary}"

    def clean(self):
        if self.salary_start_date >= self.salary_end_date:
            raise ValidationError(_('End date must be after start date'))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    image = models.ImageField(upload_to='post_images/', blank=True, null=True)
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.first_name} - {self.content[:20]}"

class Comment(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, related_name='comments', on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.first_name} - {self.content[:20]}"


class SalaryPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    base_salary = models.DecimalField(max_digits=10, decimal_places=2)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_date = models.DateField()
    pdf_file = models.FileField(upload_to='salary_slips/%Y/%m/', null=True, blank=True)

    def get_pdf_path(self):
        return os.path.join(
            settings.SALARY_SLIPS_DIR,
            str(self.user.id),
            self.payment_date.strftime('%Y'),
            self.payment_date.strftime('%m'),
            f'salary_slip_{self.id}.pdf'
        )

    def generate_pdf(self):
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from io import BytesIO

            # Create directory structure
            pdf_path = self.get_pdf_path()
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)

            # Generate PDF
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )

            story = []
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=24,
                spaceAfter=30
            )

            # Add content to PDF
            story.append(Paragraph("Payroll System", title_style))
            story.append(Paragraph("SALARY SLIP", styles["Heading2"]))
            story.append(Spacer(1, 20))

            employee_info = [
                ["Employee Name:", f"{self.user.first_name} {self.user.last_name}"],
                ["Payment Date:", f"{self.payment_date}"],
                ["Employee ID:", f"{self.user.id}"]
            ]

            t = Table(employee_info, colWidths=[120, 300])
            t.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(t)
            story.append(Spacer(1, 20))

            salary_data = [
                ["Description", "Amount"],
                ["Base Salary", f"${self.base_salary}"],
                ["Bonus", f"${self.bonus}"],
                ["Deductions", f"-${self.deduction}"],
                ["Total Payment", f"${self.total_payment}"]
            ]

            t = Table(salary_data, colWidths=[200, 200])
            t.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            story.append(t)

            doc.build(story)
            return True

        except Exception as e:
            print(f"Error generating PDF: {str(e)}")
            return False

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new:
            self.generate_pdf()

    @property
    def total_payment(self):
        return self.base_salary + self.bonus - self.deduction

    def __str__(self):
        return f"Payment for {self.user.first_name} {self.user.last_name}"

class Department(models.Model):
    id = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=255)

    def __str__(self):
        return self.department_name

class DepartmentHistory(models.Model):
    id = models.AutoField(primary_key=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return f"{self.department.department_name} - {self.employee.first_name} {self.employee.last_name}"


class TimeRecord(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_records')
    date = models.DateField(auto_now_add=True)
    punch_in = models.DateTimeField(auto_now_add=True)
    punch_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-date', '-punch_in']

    @property
    def hours_worked(self):
        if self.punch_out:
            duration = self.punch_out - self.punch_in
            return duration.total_seconds() / 3600
        return 0

    def __str__(self):
        return f"{self.user.first_name} - {self.date}"