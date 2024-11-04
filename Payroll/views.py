from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView

from Payroll.forms import PostForm
from Payroll.models import User, Post, Comment
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
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return redirect('login_form')

def register_form(request):
    return render(request, 'register.html')

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
                'status': 'Permanent' if u.job_title_id == 1 else 'Contract',
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

def settings_user(request):
    user = get_user_from_token(request)
    return render(request, 'settings.html', {
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