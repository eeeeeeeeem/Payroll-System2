from tkinter.font import names

from django.conf.urls.static import static

from . import views
from django.urls import path
from .views import RegisterView, register_form, LoginView, login_form, UserView, LogoutView, job_desk, employees, \
    all_employee, appointment, payroll, settings, send_email, settings_user, posting_user, create_post, \
    job_title_register, job_title_create, add_job, create_department, \
    create_department_history, delete_account, pay_jobs, edit_department, delete_department, edit_department_history, \
    delete_department_history, JobDeskView, JobApplicationView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register/form/', register_form, name='register_form'),
    path('register/job/', job_title_register, name='job_title_register'),
    path('job_title/create/', job_title_create, name='job_title_create'),
    path('login/', LoginView.as_view(), name='login'),
    path('login/form/', login_form, name='login_form'),
    path('dashboard/', UserView.as_view(), name='dashboard'),
    path('punch-in/', UserView.as_view(), name='punch_in'),
    path('punch-out/', UserView.as_view(), name='punch_out'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('job_desk/', job_desk, name='job_desk'),
    path('employees/', employees, name='employees'),
    path('all_employee/', all_employee, name='all_employee'),
    path('appointment/', appointment, name='appointment'),
    path('payroll/', payroll, name='payroll'),
    path('settings/', views.settings_user, name='settings_user'),
    path('posting_user/', posting_user, name='posting_user'),
    path('create_post/', create_post, name='create_post'),
    path('post_list/', views.post_list, name='post_list'),
    path('send_email/', send_email, name='send_email'),
    path('posting/', views.posting_user, name='posting_user'),
    path('post_list/like_post/<int:post_id>/', views.like_post, name='like_post'),
    path('post_list/add_comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('add_job/', add_job, name='add_job'),

    path('pay_jobs/', pay_jobs, name='pay_jobs'),
    path('add_salary/', views.add_salary, name='add_salary'),

    path('salary_payments/', views.salary_payment_list, name='salary_payment_list'),
    path('salary-payments/create/', views.salary_payment_create, name='salary_payment_create'),
    path('salary-payments/delete/<int:pk>/', views.salary_payment_delete, name='salary_payment_delete'),

    path('create_department/', create_department, name='create_department'),
    path('create_department_history/', create_department_history, name='create_department_history'),
    path('departments/', views.department_list, name='department_list'),
    path('department_histories/', views.department_history_list, name='department_history_list'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('signup/hr', views.hr_signup, name='hr_signup'),

    path('salary-slips/', views.salary_slips, name='salary_slips'),
    path('salary-slips/download/<int:payment_id>/', views.download_salary_slip, name='download_salary_slip'),
    path('salary-slips/regenerate/<int:payment_id>/', views.regenerate_pdf, name='regenerate_pdf'),
    path('request-salary-slip/', views.request_salary_slip, name='request_salary_slip'),
    path('requests/', views.view_requests, name='view_requests'),
    path('process-request/<int:request_id>/', views.process_request, name='process_request'),
    path('department/edit/<int:id>/', edit_department, name='edit_department'),
    path('department/delete/<int:id>/', delete_department, name='delete_department'),
    path('department_history/edit/<int:id>/', edit_department_history, name='edit_department_history'),
    path('department_history/delete/<int:id>/', delete_department_history, name='delete_department_history'),

    path('jobs/', JobDeskView.as_view(), name='jobs'),
    path('api/job-application/', JobApplicationView.as_view(), name='job_application'),
    path('apply-job/', views.apply_job, name='apply_job'),
    path('add-job/', views.add_job_posting, name='add_job_posting'),
    path('jobs/<int:job_id>/apply/', views.job_application, name='job_application'),
    path('application/<int:application_id>/review/', views.review_application, name='review_application'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
