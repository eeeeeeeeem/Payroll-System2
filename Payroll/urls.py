from tkinter.font import names
from . import views
from django.urls import path
from .views import RegisterView, register_form, LoginView, login_form, UserView, LogoutView, job_desk, employees, \
    all_employee, appointment, payroll, settings, send_email, settings_user, posting_user, create_post, \
    job_title_register, job_title_create, add_job, employment_terms_register, create_department, \
    create_department_history, delete_account

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
    path('add_salary/', views.add_salary, name='add_salary'),
    path('register/employment_terms/', employment_terms_register, name='employment_terms_register'),

    path('salary_payments/', views.salary_payment_list, name='salary_payment_list'),
    path('salary-payments/create/', views.salary_payment_create, name='salary_payment_create'),
    path('salary-payments/delete/<int:pk>/', views.salary_payment_delete, name='salary_payment_delete'),

    path('create_department/', create_department, name='create_department'),
    path('create_department_history/', create_department_history, name='create_department_history'),
    path('departments/', views.department_list, name='department_list'),
    path('department_histories/', views.department_history_list, name='department_history_list'),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('signup/hr', views.hr_signup, name='hr_signup'),

]
