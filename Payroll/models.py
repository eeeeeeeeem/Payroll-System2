from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
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
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    cityId = models.CharField(max_length=255)
    employement_start = models.DateField(null=True, blank=True)
    employement_end = models.DateField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    job_title = models.ForeignKey(JobTitle, on_delete=models.CASCADE, related_name='employees', default=1)

    objects = UserManager()


    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'date_of_birth', 'gender', 'address', 'cityId', 'employement_start', 'job_title', 'employement_end']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class EmploymentTerms(models.Model):
    id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="employment_terms")
    agreed_salary = models.DecimalField(max_digits=10, decimal_places=2)
    salary_start_date = models.DateField()
    salary_end_date = models.DateField()

    def __str__(self):
        return f"{self.employee.first_name} {self.employee.last_name} - {self.agreed_salary}"


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