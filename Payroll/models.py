import os
from datetime import timezone

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

    def get_username(self):
        return self.email

    @property
    def username(self):
        return self.email.split('@')[0]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def total_achievement_points(self):
        return UserAchievement.objects.filter(
            user=self,
            completed=True
        ).aggregate(
            total=models.Sum('achievement__points')
        )['total'] or 0

    @property
    def achievement_rank(self):
        points = self.total_achievement_points
        if points >= 1000:
            return "Master"
        elif points >= 500:
            return "Expert"
        elif points >= 250:
            return "Professional"
        elif points >= 100:
            return "Intermediate"
        else:
            return "Beginner"

    @property
    def next_achievements(self):
        completed_achievements = UserAchievement.objects.filter(
            user=self,
            completed=True
        ).values_list('achievement_id', flat=True)

        return Achievement.objects.exclude(
            id__in=completed_achievements
        ).order_by('points')[:5]


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


class SalarySlipRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected')
    )

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='salary_slip_requests')
    request_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    month = models.DateField(help_text="Month and year of requested salary slip")
    notes = models.TextField(blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='processed_requests', null=True, blank=True)
    processed_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Salary Slip Request - {self.employee.get_full_name()} - {self.month.strftime('%B %Y')}"

class JobPosting(models.Model):
    STATUS_CHOICES = (
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('DRAFT', 'Draft')
    )

    title = models.CharField(max_length=255)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    responsibilities = models.TextField()
    additional_info = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    deadline = models.DateField()

    def __str__(self):
        return self.title

class JobApplication(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('REVIEWED', 'Reviewed'),
        ('SHORTLISTED', 'Shortlisted'),
        ('REJECTED', 'Rejected'),
        ('ACCEPTED', 'Accepted'),
    )

    job = models.ForeignKey(JobPosting, on_delete=models.CASCADE, related_name='applications')
    applicant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='job_applications')
    applied_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    resume = models.FileField(upload_to='resumes/', null=True, blank=True)
    cover_letter = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='reviewed_applications', null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ['job', 'applicant']

    def __str__(self):
        return f"{self.applicant.get_full_name()} - {self.job.title}"


class Achievement(models.Model):
    ACHIEVEMENT_TYPES = (
        ('YEARS', 'Years of Service'),
        ('SKILL', 'Skill Mastery'),
        ('PROJECT', 'Project Completion'),
        ('TRAINING', 'Training Certification'),
        ('MENTOR', 'Mentorship'),
        ('INNOVATION', 'Innovation Award'),
    )

    TIER_CHOICES = (
        ('BRONZE', 'Bronze'),
        ('SILVER', 'Silver'),
        ('GOLD', 'Gold'),
        ('PLATINUM', 'Platinum'),
    )

    name = models.CharField(max_length=255)
    description = models.TextField()
    achievement_type = models.CharField(max_length=20, choices=ACHIEVEMENT_TYPES)
    tier = models.CharField(max_length=10, choices=TIER_CHOICES)
    points = models.IntegerField(default=0)
    icon = models.ImageField(upload_to='achievement_icons/', null=True, blank=True)
    requirements = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.tier}"

    def calculate_progress(self, user):
        """Calculate progress based on achievement type"""
        user_achievement = UserAchievement.objects.filter(user=user, achievement=self).first()

        if user_achievement:
            if user_achievement.completed:
                return 100
            return user_achievement.progress

        if self.achievement_type == 'YEARS':
            # Calculate years of service
            years = (timezone.now().date() - user.date_joined.date()).days / 365
            return min(int((years / int(self.requirements)) * 100), 100)

        elif self.achievement_type == 'PROJECT':
            # Calculate based on milestones
            milestone_count = CareerMilestone.objects.filter(user=user).count()
            required_count = int(self.requirements.split()[0])  # Assumes format "X milestones"
            return min(int((milestone_count / required_count) * 100), 100)

        elif self.achievement_type == 'SKILL':
            # Calculate based on skill level
            skill_name = self.requirements.split()[-1]  # Assumes format "Reach level X in SKILL_NAME"
            skill = SkillLevel.objects.filter(user=user, skill_name=skill_name).first()
            if skill:
                return min(int((skill.current_level / 5) * 100), 100)

        return 0


class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    earned_date = models.DateTimeField(auto_now_add=True)
    progress = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    evidence = models.TextField(null=True, blank=True)
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_achievements'
    )

    class Meta:
        unique_together = ['user', 'achievement']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.achievement.name}"

    def update_progress(self, new_progress):
        """Update progress and check for completion"""
        self.progress = min(new_progress, 100)
        if self.progress >= 100 and not self.completed:
            self.completed = True
            self.earned_date = timezone.now()
        self.save()


class CareerMilestone(models.Model):
    MILESTONE_TYPES = (
        ('PROMOTION', 'Promotion'),
        ('CERTIFICATION', 'Certification'),
        ('AWARD', 'Award'),
        ('PROJECT', 'Major Project'),
        ('TRAINING', 'Training Completion'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=255)
    description = models.TextField()
    milestone_type = models.CharField(max_length=20, choices=MILESTONE_TYPES)
    date_achieved = models.DateField()
    points_earned = models.IntegerField(default=0)
    attachments = models.FileField(upload_to='milestone_attachments/', null=True, blank=True)
    is_public = models.BooleanField(default=True)  # For sharing on profile

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.title}"


class SkillLevel(models.Model):
    LEVEL_CHOICES = (
        (1, 'Beginner'),
        (2, 'Intermediate'),
        (3, 'Advanced'),
        (4, 'Expert'),
        (5, 'Master'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='skill_levels')
    skill_name = models.CharField(max_length=255)
    current_level = models.IntegerField(choices=LEVEL_CHOICES, default=1)
    experience_points = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)
    endorsed_by = models.ManyToManyField(User, related_name='endorsed_skills')

    class Meta:
        unique_together = ['user', 'skill_name']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.skill_name} (Level {self.current_level})"