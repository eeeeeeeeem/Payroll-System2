from django import forms
from .models import Post, User


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']



class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'date_of_birth', 'gender', 'address', 'cityId', 'employement_start', 'job_title_id', 'profile_picture']