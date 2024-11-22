from calendar import monthrange
from functools import wraps
from django.contrib import messages
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.mail import send_mail
from django.conf import settings
import jwt, datetime
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, get_object_or_404, redirect
from .forms import SalaryPaymentForm
from Payroll.forms import PostForm, UserSettingsForm
from Payroll.models import User, Post, Comment, JobTitle, EmploymentTerms, SalaryPayment, TimeRecord
from Payroll.serializers import UserSerializer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import JobTitle
import logging
logger = logging.getLogger(__name__)


def hr_required(view_func):
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('login_form')

        if not request.user.is_hr():
            messages.error(request, 'Access denied. HR privileges required.')
            raise PermissionDenied('You do not have permission to access this page.')

        return view_func(request, *args, **kwargs)

    return wrapped_view

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
# Create Salary Payment
@hr_required
def salary_payment_create(request):
    if request.method == 'POST':
        form = SalaryPaymentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('salary_payment_list')
    else:
        form = SalaryPaymentForm()

    return render(request, 'salary_payment_form.html', {'form': form})

# List Salary Payments

@hr_required
def salary_payment_list(request):
    user = get_user_from_token(request)
    salary_payments = SalaryPayment.objects.all()
    return render(request, 'payroll.html', {
        'salary_payments': salary_payments,
        'profile_picture': user.profile_picture.url if user.profile_picture else None
    })

# Delete Salary Payment
def salary_payment_delete(request, pk):
    salary_payment = get_object_or_404(SalaryPayment, pk=pk)
    salary_payment.delete()
    return redirect('salary_payment_list')

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
    # Retrieve job titles for display
    job_titles = JobTitle.objects.all().order_by('start_date')

    if request.method == 'POST':
        form = UserSettingsForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            user.save()
            messages.success(request, 'Registration successful! Please log in.')
            return redirect('login_form')  # Replace 'login_form' with your actual login URL name
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserSettingsForm()

    return render(request, 'register.html', {'form': form, 'job_titles': job_titles})
class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        try:
            # Use authenticate to get the user with the correct backend
            user = authenticate(request, email=email, password=password)

            if user is None:
                raise AuthenticationFailed('Invalid email or password')

            # Update last login
            user.last_login = datetime.datetime.now(datetime.timezone.utc)
            user.save()

            # Create JWT token
            payload = {
                'id': user.id,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
                'iat': datetime.datetime.now(datetime.timezone.utc)
            }

            token = jwt.encode(payload, 'secret', algorithm='HS256')
            token = token if isinstance(token, str) else token.decode('utf-8')

            # Log the user in with the ModelBackend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            response = redirect('dashboard')
            response.set_cookie(key='jwt', value=token, httponly=True)
            return response

        except Exception as e:
            print(f"Login error: {str(e)}")  # Debug print
            raise AuthenticationFailed('Login failed')

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
    def calculate_month_stats(self, user):
        now = timezone.now()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, last_day = monthrange(now.year, now.month)
        last_date = now.replace(day=last_day)

        try:
            # Get all time records for current month
            time_records = TimeRecord.objects.filter(
                user=user,
                date__gte=first_day.date(),
                date__lte=last_date.date()
            )

            STANDARD_HOURS_PER_DAY = 8

            # Calculate working days in current month (excluding weekends)
            working_days = len([x for x in range(1, last_day + 1)
                                if datetime.datetime(now.year, now.month, x).weekday() < 5])

            # Calculate total required hours for the month
            total_required_hours = working_days * STANDARD_HOURS_PER_DAY

            # Calculate actual worked hours
            total_worked_hours = sum(record.hours_worked for record in time_records)

            # Calculate overtime and daily records
            daily_records = {}
            for record in time_records:
                date_str = record.date.strftime('%Y-%m-%d')
                if date_str not in daily_records:
                    daily_records[date_str] = 0
                daily_records[date_str] += record.hours_worked

            overtime_hours = sum(max(0, hours - STANDARD_HOURS_PER_DAY)
                                 for hours in daily_records.values())

            shortage_hours = max(0, total_required_hours - (total_worked_hours - overtime_hours))

            if total_required_hours > 0:
                worked_percentage = min(100, (total_worked_hours / total_required_hours) * 100)
                shortage_percentage = (shortage_hours / total_required_hours) * 100
                overtime_percentage = (overtime_hours / total_required_hours) * 100
            else:
                worked_percentage = 0
                shortage_percentage = 0
                overtime_percentage = 0

            return {
                'total_hours': round(total_required_hours, 1),
                'worked_hours': round(total_worked_hours, 1),
                'shortage_hours': round(shortage_hours, 1),
                'overtime_hours': round(overtime_hours, 1),
                'worked_percentage': round(worked_percentage, 1),
                'shortage_percentage': round(shortage_percentage, 1),
                'overtime_percentage': round(overtime_percentage, 1),
            }
        except Exception as e:
            print(f"Error calculating month stats: {e}")
            return {
                'total_hours': 216.0,
                'worked_hours': 189.0,
                'shortage_hours': 23.0,
                'overtime_hours': 56.0,
                'worked_percentage': 87,
                'shortage_percentage': 10,
                'overtime_percentage': 25,
            }

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

        month_stats = self.calculate_month_stats(user)

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
            'users': user_data,
            'last_login': user.last_login,
            'punch_out': user.punch_out_time,
            'month_stats': month_stats
        })

    def post(self, request):
        action = request.POST.get('action')

        if action == 'punch_in':
            return self.handle_punch_in(request)
        elif action == 'punch_out':
            return self.handle_punch_out(request)

        return redirect('dashboard')

    def handle_punch_in(self, request):
        token = request.COOKIES.get('jwt')
        if not token:
            raise AuthenticationFailed('Unauthenticated')

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            user = User.objects.filter(id=payload['id']).first()

            # Create new time record
            TimeRecord.objects.create(
                user=user,
                date=timezone.now().date(),
                punch_in=timezone.now(),
                punch_out=None
            )

            # Reset punch out time
            user.punch_out_time = None
            user.save()

            return redirect('dashboard')
        except Exception as e:
            print(f"Error in punch_in: {e}")
            return redirect('dashboard')

    def handle_punch_out(self, request):
        token = request.COOKIES.get('jwt')
        if not token:
            raise AuthenticationFailed('Unauthenticated')

        try:
            payload = jwt.decode(token, 'secret', algorithms=['HS256'])
            user = User.objects.filter(id=payload['id']).first()
            latest_record = TimeRecord.objects.filter(
                user=user,
                punch_out__isnull=True
            ).latest('punch_in')

            current_time = timezone.now()
            latest_record.punch_out = current_time
            latest_record.save()

            user.punch_out_time = current_time
            user.save()
            return redirect('dashboard')
        except Exception as e:
            print(f"Error in punch_out: {e}")
            return redirect('dashboard')

class LogoutView(APIView):
    def post(self, request):

        user = get_user_from_token(request)
        user.punch_out_time = datetime.datetime.now(datetime.timezone.utc)
        user.save()


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

@hr_required
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

from Payroll.forms import DepartmentForm, DepartmentHistoryForm

def create_department(request):
    user = get_user_from_token(request)
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('all_employee')
    else:
        form = DepartmentForm()
    return render(request, 'create_department.html', {
        'form': form,
        'profile_picture': user.profile_picture.url if user.profile_picture else None,
        'first_name': user.first_name,
        'last_name': user.last_name
    })

def create_department_history(request):
    if request.method == 'POST':
        form = DepartmentHistoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('all_employee')
    else:
        form = DepartmentHistoryForm()
    return render(request, 'create_department_history.html', {'form': form})

from Payroll.models import Department, DepartmentHistory

def department_list(request):
    departments = Department.objects.all()
    return render(request, 'department_list.html', {'departments': departments})

def department_history_list(request):
    department_histories = DepartmentHistory.objects.all()
    return render(request, 'department_history_list.html', {'department_histories': department_histories})

from django.urls import reverse

def create_department(request):
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('department_list'))
    else:
        form = DepartmentForm()
    return render(request, 'create_department.html', {'form': form})



def create_department_history(request):
    if request.method == 'POST':
        form = DepartmentHistoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('department_history_list'))
    else:
        form = DepartmentHistoryForm()
    return render(request, 'create_department_history.html', {'form': form})


@login_required(login_url='login_form')
def delete_account(request):
    if request.method == 'POST':
        try:
            # Store email instead of username since that's your user identifier
            user_email = request.user.email
            user = request.user

            # Print debug information
            print(f"Attempting to delete user: {user_email}")
            print(f"User ID: {user.id}")

            # Delete the user first, then logout
            user.delete()
            logout(request)

            messages.success(request, f'Account {user_email} has been successfully deleted.')
            return redirect('login_form')
        except Exception as e:
            print(f"Error deleting account: {str(e)}")  # Debug print
            messages.error(request, f'Failed to delete account: {str(e)}')
            return redirect('settings_user')
    return redirect('settings_user')


def hr_signup(request):
    if request.method == 'POST':
        try:
            email = request.POST['email']
            password = request.POST['password']
            first_name = request.POST['first_name']
            last_name = request.POST['last_name']
            date_of_birth = request.POST['date_of_birth']
            gender = request.POST['gender']
            address = request.POST['address']
            cityId = request.POST['cityId']
            employement_start = request.POST['employement_start']
            employement_end = request.POST.get('employement_end')
            job_title_id = request.POST['job_title']
            profile_picture = request.FILES.get('profile_picture')

            # Create HR user
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth,
                gender=gender,
                address=address,
                cityId=cityId,
                employement_start=employement_start,
                employement_end=employement_end if employement_end else None,
                job_title_id=job_title_id,
                profile_picture=profile_picture,
                role='HR'  # Set role as HR
            )

            messages.success(request, 'HR account created successfully! Please login.')
            return redirect('login_form')

        except Exception as e:
            messages.error(request, f'Error creating HR account: {str(e)}')
            return redirect('hr_signup')

    # GET request - show the form
    job_titles = JobTitle.objects.all()
    return render(request, 'hr_signup.html', {'job_titles': job_titles})


