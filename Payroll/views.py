import os
from calendar import monthrange
from functools import wraps
from django.views.generic import ListView

from django.contrib import messages
from django.contrib.auth import logout, login, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models import Count
from django.http import JsonResponse, FileResponse, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST, require_http_methods
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

from Payroll_System.wsgi import application
from .forms import SalaryPaymentForm, SalarySlipRequestForm, JobPostingForm
from Payroll.forms import PostForm, UserSettingsForm
from Payroll.models import User, Post, Comment, JobTitle, EmploymentTerms, SalaryPayment, TimeRecord, SalarySlipRequest, \
    JobPosting, JobApplication
from Payroll.serializers import UserSerializer
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import JobTitle
from .models import Department
from .forms import DepartmentForm
from .models import DepartmentHistory
from .forms import DepartmentHistoryForm
from Payroll.forms import DepartmentForm, DepartmentHistoryForm
from Payroll.models import Department, DepartmentHistory
from django.urls import reverse
import logging
logger = logging.getLogger(__name__)


@login_required
def applications_to_review(request):
    if not request.user.is_hr():
        messages.error(request, "You don't have permission to review applications.")
        return redirect('job_desk')

    applications = JobApplication.objects.select_related(
        'job',
        'applicant',
        'reviewed_by'
    ).order_by('-applied_at')

    # Filter by status if provided
    status = request.GET.get('status')
    if status:
        applications = applications.filter(status=status)

    return render(request, 'review_applications.html', {
        'applications': applications,
        'status_choices': JobApplication.STATUS_CHOICES
    })


@login_required
def review_application(request, application_id):
    application = get_object_or_404(JobApplication, id=application_id)

    if not request.user.is_hr:
        messages.error(request, "You don't have permission to review applications.")
        return redirect('job_list')

    if request.method == 'POST':
        # Update application status and notes
        status = request.POST.get('status')
        notes = request.POST.get('notes', '')

        if status in dict(JobApplication.STATUS_CHOICES):
            application.status = status
            application.notes = notes
            application.reviewed_by = request.user
            application.reviewed_at = timezone.now()
            application.save()

            messages.success(request, 'Application review saved successfully.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid status selected.')

    # Prepare context for template
    context = {
        'application': application,
        'status_choices': JobApplication.STATUS_CHOICES,
    }

    return render(request, 'review_applications.html', context)


def job_application(request, job_id):
    job = get_object_or_404(JobPosting, id=job_id)

    if request.method == 'POST':
        cover_letter = request.POST.get('cover_letter')
        resume = request.FILES.get('resume')

        JobApplication.objects.create(
            job=job,
            applicant=request.user,
            cover_letter=cover_letter,
            resume=resume,
            status='PENDING'
        )

        return redirect('dashboard')  # Redirect to jobs list after successful application

    return render(request, 'job_application.html', {'job': job})


@login_required
def add_job_posting(request):
    if not request.user.is_hr():
        messages.error(request, "You don't have permission to post jobs.")
        return redirect('job_desk')

    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            try:
                job = form.save(commit=False)
                job.created_by = request.user
                job.save()
                messages.success(request, f'Job "{job.title}" has been posted successfully!')
                return redirect('job_desk')
            except Exception as e:
                messages.error(request, f'Error creating job: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = JobPostingForm()

    return render(request, 'add_job.html', {'form': form})


def apply_job(request):
    if request.method == 'POST':
        job_id = request.POST.get('job_id')
        cover_letter = request.POST.get('cover_letter')
        resume = request.FILES.get('resume')

        if not job_id:
            return JsonResponse({'error': 'Job ID is required'}, status=400)
        try:

            job = get_object_or_404(JobPosting, id=job_id)

            JobApplication.objects.create(
                job=job,
                applicant = request.user,
                cover_letter=cover_letter,
                resume=resume
            )
            return JsonResponse({'message': 'Application submitted successfully'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Invalid request method'}, status=405)


class JobDeskView(LoginRequiredMixin, ListView):
    model = JobPosting
    template_name = 'job_deskkk.html'
    context_object_name = 'jobs'

    def get_queryset(self):
        queryset = JobPosting.objects.filter(status='OPEN').select_related('department')

        # Add prefetch_related for HR users
        if self.request.user.is_hr:
            queryset = queryset.prefetch_related(
                'applications',
                'applications__applicant'
            )

        department = self.request.GET.get('department')
        if department:
            queryset = queryset.filter(department__id=department)

        salary_min = self.request.GET.get('salary_min')
        if salary_min:
            queryset = queryset.filter(salary_min__gte=salary_min)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['departments'] = Department.objects.annotate(
            job_count=Count('jobposting')
        )

        if self.request.user.is_authenticated:
            context['user_applications'] = JobApplication.objects.filter(
                applicant=self.request.user
            ).values_list('job_id', flat=True)

        return context


class JobApplicationView(View):
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Authentication required'}, status=401)

        job_id = request.POST.get('job_id')
        if not job_id:
            return JsonResponse({'error': 'Job ID is required'}, status=400)

        try:
            job = JobPosting.objects.get(id=job_id, status='OPEN')

            if JobApplication.objects.filter(job=job, applicant=request.user).exists():
                return JsonResponse({'error': 'You have already applied for this job'}, status=400)

            application = JobApplication.objects.create(
                job=job,
                applicant=request.user,
                cover_letter=request.POST.get('cover_letter', '')
            )

            return JsonResponse({
                'status': 'success',
                'message': 'Application submitted successfully',
                'application_id': application.id
            })

        except JobPosting.DoesNotExist:
            return JsonResponse({'error': 'Job not found or closed'}, status=404)


@login_required
def request_salary_slip(request):
    print("Method:", request.method)  # Debug print

    if request.method == 'POST':
        print("POST data:", request.POST)  # Debug print
        selected_month = int(request.POST.get('month'))
        selected_year = int(request.POST.get('year'))
        notes = request.POST.get('notes', '')

        print(f"Month: {selected_month}, Year: {selected_year}, Notes: {notes}")  # Debug print

        try:
            request_date = datetime.datetime(selected_year, selected_month, 1).date()

            # Check for existing request
            existing_request = SalarySlipRequest.objects.filter(
                employee=request.user,
                month__year=selected_year,
                month__month=selected_month
            ).exists()

            print(f"Existing request: {existing_request}")  # Debug print

            if existing_request:
                messages.error(request, 'You have already submitted a request for this month.')
            else:
                # Create new request
                new_request = SalarySlipRequest.objects.create(
                    employee=request.user,
                    month=request_date,
                    notes=notes,
                    status='PENDING'
                )
                print(f"New request created: {new_request}")  # Debug print
                messages.success(request, 'Salary slip request submitted successfully.')
                return redirect('view_requests')

        except Exception as e:
            print(f"Error occurred: {str(e)}")  # Debug print
            messages.error(request, f'Error submitting request: {str(e)}')

    # For GET request or if POST fails
    current_date = datetime.datetime.now()
    context = {
        'current_month': current_date.month,
        'current_year': current_date.year,
        'years': range(current_date.year - 2, current_date.year + 1)
    }

    return render(request, 'request_salary_slip.html', context)

@login_required
def view_requests(request):  # 'request' is the parameter name
    if request.user.role == 'HR':
        salary_requests = SalarySlipRequest.objects.filter(status='PENDING').order_by('-request_date')  # Changed variable name to salary_requests
        template = 'hr_requests.html'
    else:
        salary_requests = SalarySlipRequest.objects.filter(employee=request.user).order_by('-request_date')  # Changed variable name to salary_requests
        template = 'employee_requests.html'

    return render(request, template, {'requests': salary_requests})


@login_required
def process_request(request, request_id):
    if request.user.role != 'HR':
        messages.error(request, 'You do not have permission to process requests.')
        return redirect('dashboard')

    slip_request = get_object_or_404(SalarySlipRequest, id=request_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action in ['APPROVED', 'REJECTED']:
            slip_request.status = action
            slip_request.processed_by = request.user
            slip_request.processed_date = timezone.now()
            slip_request.save()

            if action == 'APPROVED':
                messages.success(request,
                               f'Request approved for {slip_request.employee.get_full_name()}')
            else:
                messages.info(request, f'Request rejected for {slip_request.employee.get_full_name()}')

    return redirect('view_requests')

@login_required
def regenerate_pdf(request, payment_id):
    payment = get_object_or_404(SalaryPayment, id=payment_id, user=request.user)
    if payment.generate_pdf():
        messages.success(request, 'PDF regenerated successfully.')
    else:
        messages.error(request, 'Failed to regenerate PDF.')
    return redirect('salary_slips')

def generate_pdf(self):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        import os

        print(f"Generating PDF for payment {self.id}")  # Debug print

        buffer = BytesIO()

        # ... your existing PDF generation code ...

        pdf = buffer.getvalue()
        buffer.close()

        # Create the filename and full path
        filename = f'salary_slip_{self.user.email}_{self.payment_date.strftime("%Y_%m")}.pdf'

        # Ensure the upload directory exists
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'salary_slips',
                                  self.payment_date.strftime('%Y'),
                                  self.payment_date.strftime('%m'))
        os.makedirs(upload_dir, exist_ok=True)

        print(f"Saving PDF to {upload_dir}/{filename}")  # Debug print

        # Save the PDF
        self.pdf_file.save(filename, ContentFile(pdf), save=True)

        print(f"PDF generated successfully: {self.pdf_file.path}")  # Debug print

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")  # Debug print
        raise

def ensure_media_dirs():
    media_root = settings.MEDIA_ROOT
    salary_slips_dir = os.path.join(media_root, 'salary_slips')

    # Create base media directory
    if not os.path.exists(media_root):
        os.makedirs(media_root)

    # Create salary slips directory
    if not os.path.exists(salary_slips_dir):
        os.makedirs(salary_slips_dir)


@login_required
def salary_slips(request):
    salary_payments = request.user.get_salary_slips()
    return render(request, 'salary_slips.html', {
        'salary_payments': salary_payments,
        'title': 'My Salary Slips'
    })


@login_required
def download_salary_slip(request, payment_id):
    payment = get_object_or_404(SalaryPayment, id=payment_id, user=request.user)
    pdf_path = payment.get_pdf_path()

    if os.path.exists(pdf_path):
        return FileResponse(
            open(pdf_path, 'rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=f'salary_slip_{payment.payment_date.strftime("%Y_%m")}.pdf'
        )

    if payment.generate_pdf():
        return FileResponse(
            open(pdf_path, 'rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=f'salary_slip_{payment.payment_date.strftime("%Y_%m")}.pdf'
        )

    return HttpResponse("Unable to generate PDF", status=500)

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
    ensure_media_dirs()
    if request.method == 'POST':
        form = SalaryPaymentForm(request.POST)
        if form.is_valid():
            payment = form.save()
            payment.generate_pdf()
            payment.save()
            messages.success(request, 'Salary payment created successfully.')
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

def salary_payment_update(request, pk):
    payment = get_object_or_404(SalaryPayment, pk=pk)
    if request.method == 'POST':
        form = SalaryPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            return redirect('salary_payment_list')
    else:
        form = SalaryPaymentForm(instance=payment)
    return render(request, 'salary_payment_update.html', {'form': form})

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
            try:
                user = form.save(commit=False)
                user.is_active = True  # Set user as active
                user.save()
                messages.success(request, 'Registration successful! Please log in.')
                return redirect('login_form')
            except Exception as e:
                messages.error(request, f'Registration failed: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = UserSettingsForm()

    return render(request, 'register.html', {
        'form': form,
        'job_titles': job_titles
    })


class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        print(f"Login attempt with email: {email}")  # Debug print

        try:
            # First check if user exists
            try:
                user = User.objects.get(email=email)
                print(f"Found user: {user.email}")
            except User.DoesNotExist:
                print("User not found")
                raise AuthenticationFailed('Invalid email or password')

            # Use authenticate with username=email
            authenticated_user = authenticate(request, username=email, password=password)
            print(f"Authentication result: {authenticated_user}")

            if authenticated_user is None:
                print("Authentication failed")
                raise AuthenticationFailed('Invalid email or password')

            # Update last login
            authenticated_user.last_login = datetime.datetime.now(datetime.timezone.utc)
            authenticated_user.save()

            # Create JWT token
            payload = {
                'id': authenticated_user.id,
                'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=60),
                'iat': datetime.datetime.now(datetime.timezone.utc)
            }

            token = jwt.encode(payload, 'secret', algorithm='HS256')

            # Log the user in
            login(request, authenticated_user)

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
    def get_dashboard_stats(self, user):
        current_date = timezone.now().date()
        thirty_days_ago = current_date - datetime.timedelta(days=30)

        try:
            # Total active employees
            total_employees = User.objects.filter(
                is_active=True,
                role='EMPLOYEE'
            ).count()

            # Recent employment terms
            recent_job_views = EmploymentTerms.objects.filter(
                salary_start_date__gte=thirty_days_ago
            ).count()

            # Recently joined employees
            recent_joins = User.objects.filter(
                employement_start__gte=thirty_days_ago
            ).count()

            # Recently resigned employees
            resigned_employees = User.objects.filter(
                employement_end__gte=thirty_days_ago,
                employement_end__lte=current_date
            ).count()

            # Previous period calculations
            previous_period = current_date - datetime.timedelta(days=60)

            prev_total = User.objects.filter(
                is_active=True,
                role='EMPLOYEE',
                employement_start__lte=thirty_days_ago
            ).count()

            prev_views = EmploymentTerms.objects.filter(
                salary_start_date__range=[previous_period, thirty_days_ago]
            ).count()

            prev_joins = User.objects.filter(
                employement_start__range=[previous_period, thirty_days_ago]
            ).count()

            prev_resigned = User.objects.filter(
                employement_end__range=[previous_period, thirty_days_ago]
            ).count()

            def calculate_percentage_change(current, previous):
                if previous == 0:
                    return 100 if current > 0 else 0
                return ((current - previous) / previous) * 100

            return {
                'total_employees': {
                    'value': total_employees,
                    'change': round(calculate_percentage_change(total_employees, prev_total), 1)
                },
                'job_views': {
                    'value': recent_job_views,
                    'change': round(calculate_percentage_change(recent_job_views, prev_views), 1)
                },
                'jobs_applied': {
                    'value': recent_joins,
                    'change': round(calculate_percentage_change(recent_joins, prev_joins), 1)
                },
                'resigned_employees': {
                    'value': resigned_employees,
                    'change': round(calculate_percentage_change(resigned_employees, prev_resigned), 1)
                }
            }
        except Exception as e:
            print(f"Error calculating dashboard stats: {e}")
            return {
                'total_employees': {'value': 0, 'change': 0},
                'job_views': {'value': 0, 'change': 0},
                'jobs_applied': {'value': 0, 'change': 0},
                'resigned_employees': {'value': 0, 'change': 0}
            }

    def calculate_month_stats(self, user):
        now = timezone.now()
        first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        _, last_day = monthrange(now.year, now.month)
        last_date = now.replace(day=last_day)

        try:
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
        dashboard_stats = self.get_dashboard_stats(user)

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
            'month_stats': month_stats,
            'dashboard_stats': dashboard_stats
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
    return render(request, 'job_deskkk.html')


def pay_jobs(request):
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

def department_list(request):
    departments = Department.objects.all()
    return render(request, 'department_list.html', {'departments': departments})

def department_history_list(request):
    department_histories = DepartmentHistory.objects.all()
    return render(request, 'department_history_list.html', {'department_histories': department_histories})


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



def edit_department(request, id):
    department = get_object_or_404(Department, id=id)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            form.save()
            return redirect('department_list')
    else:
        form = DepartmentForm(instance=department)
    return render(request, 'edit_department.html', {'form': form})

def delete_department(request, id):
    department = get_object_or_404(Department, id=id)
    if request.method == 'POST':
        department.delete()
        return redirect('department_list')
    return render(request, 'delete_department.html', {'department': department})




def edit_department_history(request, id):
    history = get_object_or_404(DepartmentHistory, id=id)
    if request.method == 'POST':
        form = DepartmentHistoryForm(request.POST, instance=history)
        if form.is_valid():
            form.save()
            return redirect('department_history_list')
    else:
        form = DepartmentHistoryForm(instance=history)
    return render(request, 'edit_department_history.html', {'form': form})

def delete_department_history(request, id):
    history = get_object_or_404(DepartmentHistory, id=id)
    if request.method == 'POST':
        history.delete()
        return redirect('department_history_list')
    return render(request, 'delete_department_history.html', {'history': history})