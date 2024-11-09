from django import forms
from Payroll.models import User, Post, JobTitle


class UserSettingsForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    job_title = forms.ModelChoiceField(queryset=JobTitle.objects.all(), empty_label=None)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'date_of_birth', 'gender', 'address', 'cityId',
                  'employement_start', 'employement_end', 'profile_picture', 'job_title', 'password']


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']