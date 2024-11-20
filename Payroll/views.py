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
from django.core.mail import send_mail
from django.conf import settings
import jwt, datetime
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect

from Payroll.forms import PostForm, UserSettingsForm
from Payroll.models import User, Post, Comment, JobTitle, EmploymentTerms, SalaryPayment
from Payroll.serializers import UserSerializer


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

# List salary payments
# List all salary payments
def salary_payment_list(request):
    salary_payments = SalaryPayment.objects.all()
    # Add a calculated total_payment field to each object
    for payment in salary_payments:
        payment.total_payment = payment.base_salary + payment.bonus - payment.deduction
    return render(request, 'payroll.html', {'salary_payments': salary_payments})

# Create a new salary payment
def salary_payment_create(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        base_salary = request.POST.get('base_salary')
        bonus = request.POST.get('bonus')
        deduction = request.POST.get('deduction')
        payment_date = request.POST.get('payment_date')

        user = get_object_or_404(User, id=user_id)
        salary_payment = SalaryPayment(
            user=user,
            base_salary=base_salary,
            bonus=bonus,
            deduction=deduction,
            payment_date=payment_date
        )
        salary_payment.save()
        return HttpResponseRedirect(reverse('salary_payment_list'))

    users = User.objects.all()
    return render(request, 'salary_payment_form.html', {'users': users})


# Delete a salary payment
def salary_payment_delete(request, pk):
    salary_payment = get_object_or_404(SalaryPayment, pk=pk)
    salary_payment.delete()
    return HttpResponseRedirect(reverse('salary_payment_list'))

def settings_user(request):
    try:
        user = get_user_from_token(request)
        print(f"User retrieved: {user.email}")
    except AuthenticationFailed:
        return redirect('login_form')

    # Get the latest employment terms
    latest_employment_terms = EmploymentTerms.objects.filter(
        employee=user
    ).order_by('-salary_start_date').first()

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            user = form.save()

            # Don't update employment terms from settings page
            messages.success(request, 'Profile updated successfully!')
            return redirect('settings_user')
        else:
            messages.error(request, 'Error updating profile. Please check the form.')
    else:
        # Initialize form with user data and latest employment terms
        initial_data = {
            'salary_start_date': latest_employment_terms.salary_start_date if latest_employment_terms else None,
            'salary_end_date': latest_employment_terms.salary_end_date if latest_employment_terms else None,
            'agreed_salary': latest_employment_terms.agreed_salary if latest_employment_terms else None,
        }
        form = UserSettingsForm(instance=user, initial=initial_data)

    return render(request, 'settings.html', {
        'form': form,
        'user': user,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'profile_picture': user.profile_picture.url if user.profile_picture else None,
        'employment_terms': latest_employment_terms,
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

    try:
        employment_terms = EmploymentTerms.objects.filter(employee=user).order_by('-salary_start_date')

        context = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'employment_terms': employment_terms,
            'user': user
        }

        if request.method == 'POST' and 'add_salary' in request.POST:
            agreed_salary = request.POST.get('agreed_salary')
            start_date = request.POST.get('salary_start_date')
            end_date = request.POST.get('salary_end_date')

            if not all([agreed_salary, start_date, end_date]):
                messages.error(request, 'All fields are required')
                return render(request, 'job_desk.html', context)

            try:
                EmploymentTerms.objects.create(
                    employee=user,
                    agreed_salary=agreed_salary,
                    salary_start_date=start_date,
                    salary_end_date=end_date
                )
                messages.success(request, 'Salary information added successfully!')
                return redirect('job_desk')
            except Exception as e:
                messages.error(request, f'Error adding salary information: {str(e)}')
                return render(request, 'job_desk.html', context)

        return render(request, 'job_desk.html', context)

    except Exception as e:
        messages.error(request, f'An error occurred: {str(e)}')
        return render(request, 'job_desk.html', {'error': str(e)})

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

def employment_terms_register(request):
    return render(request, 'employment_terms.html')
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


def add_salary(request):
    try:
        user = get_user_from_token(request)

        if request.method == 'POST':
            try:
                # Add validation for dates
                start_date = request.POST['salary_start_date']
                end_date = request.POST['salary_end_date']

                # Use the user from JWT token instead of request.user
                EmploymentTerms.objects.create(
                    employee=user,  # Changed from request.user to user
                    agreed_salary=request.POST['agreed_salary'],
                    salary_start_date=start_date,
                    salary_end_date=end_date
                )
                return JsonResponse({'message': 'Salary added successfully'}, status=200)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)

    except AuthenticationFailed as e:
        return JsonResponse({'error': str(e)}, status=401)

    return redirect('dashboard')





