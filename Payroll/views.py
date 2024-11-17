from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from Payroll.forms import PostForm, UserSettingsForm
from Payroll.models import User, Post, Comment, JobTitle
from Payroll.serializers import UserSerializer
import jwt, datetime
from django.core.mail import send_mail
from django.conf import settings


def create_post(request):
    token = request.COOKIES.get('jwt')
    if not token:
        raise AuthenticationFailed("Unauthenticated")

    try:
        payload = jwt.decode(token, 'secret', algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed("Unauthenticated")

    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = User.objects.get(id=payload['id'])  # Setting the user from the token payload
            post.save()
            return redirect('posting_user')
    else:
        form = PostForm()
    return render(request, 'posting.html', {'form': form})
def post_list(request):
    user = get_user_from_token(request)
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'posting.html', {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'profile_picture': user.profile_picture.url if user.profile_picture else None,
        'posts': posts
    })

def like_post(request, post_id):
    user = get_user_from_token(request)
    post = Post.objects.get(id=post_id)
    if user in post.likes.all():
        post.likes.remove(user)
    else:
        post.likes.add(user)
    return JsonResponse({'likes_count': post.likes.count()})

def add_comment(request, post_id):
    user = get_user_from_token(request)
    post = Post.objects.get(id=post_id)
    content = request.POST.get('content')
    if not content:
        return JsonResponse({'error': 'Content cannot be empty'}, status=400)
    comment = Comment.objects.create(author=user, post=post, content=content)
    return JsonResponse({
        'author': user.first_name,
        'content': comment.content
    })

def settings_user(request):
    try:
        user = get_user_from_token(request)
    except AuthenticationFailed:
        return redirect('login_form')

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return redirect('settings_user')
    else:
        form = UserSettingsForm(instance=user)

    return render(request, 'settings.html', {
        'form': form,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'profile_picture': user.profile_picture.url if user.profile_picture else None
    })


def posting_user(request):
    user = get_user_from_token(request)
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'posting.html', {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'profile_picture': user.profile_picture.url if user.profile_picture else None,
        'posts': posts
    })
def send_email(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        email = request.POST['email']
        concern = request.POST['concern']

        subject = f"New Concern from {first_name} {last_name}"
        message = f"First Name: {first_name}\nLast Name: {last_name}\nEmail: {email}\n\n{concern}"
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = ['sijeynoster@gmail.com']

        send_mail(subject, message, from_email, recipient_list)

        return redirect('homepage')

    return render(request, 'homepage.html')

class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return redirect('login_form')
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def register_form(request):
    job_titles = JobTitle.objects.all().order_by('start_date')

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login_form')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserSettingsForm()

    return render(request, 'register.html', {'form': form, 'job_titles': job_titles})
class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        user = User.objects.filter(email=email).first()

        if user is None:
            raise AuthenticationFailed('User not found')

        if not user.check_password(password):
            raise AuthenticationFailed('Incorrect password')

        user.last_login = datetime.datetime.now(datetime.timezone.utc)  # Update last_login
        user.save()

        payload = {
            'id': user.id,
            'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
            'iat': datetime.datetime.now(datetime.timezone.utc)
        }

        token = jwt.encode(payload, 'secret', algorithm='HS256')
        token = token if isinstance(token, str) else token.decode('utf-8')

        response = redirect('dashboard')
        response.set_cookie(key='jwt', value=token, httponly=True)

        return response

def calculate_discipline(age):
    if isinstance(age, int):
        if age >= 18:
            return f"{80 + (age % 11)}"
        else:
            return f"{10 + (age % 41)}"
    return "N/A"

def login_form(request):
    return render(request, 'login.html')

def calculate_age(born):
    if born is None:
        return "N/A"

    if isinstance(born, datetime.datetime):
        born = born.date()

    today = datetime.date.today()

    if born > today:
        return "N/A"
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

class UserView(APIView):
    def get(self, request):
        token = request.COOKIES.get('jwt')

        if not token:
            raise AuthenticationFailed('Unauthenticated')

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Unauthenticated')

        user = User.objects.filter(id=payload['id']).first()
        serializer = UserSerializer(user)

        users = User.objects.all()
        user_data = [
            {
                'name': f"{u.first_name} {u.last_name}",
                'department': u.job_title_id,
                'age': calculate_age(u.date_of_birth),
                'discipline': calculate_discipline(calculate_age(u.date_of_birth)),
                'status': 'Permanent' if u.job_title_id % 2 == 0 else 'Contract',
                'profile_picture': u.profile_picture.url if u.profile_picture else None
            }
            for u in users
        ]

        return render(request, 'dashboard.html', {
            'first_name': serializer.data['first_name'],
            'last_name': serializer.data['last_name'],
            'profile_picture': serializer.data['profile_picture'],
            'users': user_data
        })

class LogoutView(APIView):
    def post(self, request):
        response = redirect('login_form')
        response.delete_cookie('jwt')
        return response

def get_user_from_token(request):
    token = request.COOKIES.get('jwt')

    if not token:
        raise AuthenticationFailed('Unauthenticated')

    try:
        payload = jwt.decode(token, 'secret', algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise AuthenticationFailed('Unauthenticated')

    user = User.objects.filter(id=payload['id']).first()
    return user

def Homepage(request):
    return render(request, 'homepage.html')

def job_desk(request):
    user = get_user_from_token(request)
    return render(request, 'job_desk.html', {
        'first_name': user.first_name,
        'last_name': user.last_name
    })

def employees(request):
    user = get_user_from_token(request)
    return render(request, 'employees.html', {
        'first_name': user.first_name,
        'last_name': user.last_name
    })

def all_employee(request):
    user = get_user_from_token(request)
    return render(request, 'all_employee.html', {
        'first_name': user.first_name,
        'last_name': user.last_name
    })

def appointment(request):
    user = get_user_from_token(request)
    return render(request, 'appointment.html', {
        'first_name': user.first_name,
        'last_name': user.last_name
    })

def payroll(request):
    user = get_user_from_token(request)
    return render(request, 'payroll.html', {
        'first_name': user.first_name,
        'last_name': user.last_name
    })


def posting_user(request):
    user = get_user_from_token(request)
    return render(request, 'posting.html', {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'profile_picture': user.profile_picture.url if user.profile_picture else None
    })


#JOB TITLE MODEL
def job_title_register(request):
    return render(request, 'job_title.html')


def job_title_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if title and start_date and end_date:
            JobTitle.objects.create(title=title, start_date=start_date, end_date=end_date)
            return redirect('register_form')
        else:
            return render(request, 'job_title.html', {'error': 'All fields are required'})

    return render(request, 'job_title.html')

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import JobTitle

@login_required
def add_job(request):
    if request.method == 'POST':
        title = request.POST['title']
        location = request.POST['location']
        job_type = request.POST['job_type']
        salary = request.POST['salary']
        description = request.POST['description']

        JobTitle.objects.create(
            title=title,
            location=location,
            job_type=job_type,
            salary=salary,
            description=description
        )
        return redirect('job_desk')
    return render(request, 'job_desk.html')
def all_employee(request):
    user = get_user_from_token(request)
    employees = User.objects.all()
    employee_data = [
        {
            'first_name': emp.first_name,
            'last_name': emp.last_name,
            'profile_picture': emp.profile_picture.url if emp.profile_picture else None,
            'department': emp.job_title_id,
            'age': calculate_age(emp.date_of_birth),
            'discipline': calculate_discipline(calculate_age(emp.date_of_birth)),
            'status': 'Permanent' if emp.job_title_id % 2 == 0 else 'Contract'
        }
        for emp in employees
    ]
    return render(request, 'all_employee.html', {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'employees': employee_data
    })





