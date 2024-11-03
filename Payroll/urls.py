from tkinter.font import names

from django.urls import path
from .views import RegisterView, register_form, LoginView, login_form, UserView, LogoutView, job_desk, employees, \
    all_employee, appointment, payroll, settings, send_email, settings_user

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('register/form/', register_form, name='register_form'),
    path('login/', LoginView.as_view(), name='login'),
    path('login/form/', login_form, name='login_form'),
    path('dashboard/', UserView.as_view(), name='dashboard'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('job_desk/', job_desk, name='job_desk'),
    path('employees/', employees, name='employees'),
    path('all_employee/', all_employee, name='all_employee'),
    path('appointment/', appointment, name='appointment'),
    path('payroll/', payroll, name='payroll'),
    path('settings/', settings_user, name='settings'),
    path('send_email/', send_email, name='send_email'),
]
