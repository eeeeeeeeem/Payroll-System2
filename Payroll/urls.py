from tkinter.font import names
from . import views
from django.urls import path
from .views import RegisterView, register_form, LoginView, login_form, UserView, LogoutView, job_desk, employees, \
    all_employee, appointment, payroll, settings, send_email, settings_user, posting_user, create_post

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
    path('posting_user/', posting_user, name='posting_user'),
    path('create_post/', create_post, name='create_post'),
    path('post_list/', views.post_list, name='post_list'),
    path('send_email/', send_email, name='send_email'),
    path('posting/', views.posting_user, name='posting_user'),
    path('post_list/like_post/<int:post_id>/', views.like_post, name='like_post'),
    path('post_list/add_comment/<int:post_id>/', views.add_comment, name='add_comment'),
]
