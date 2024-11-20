from django import forms
from Payroll.models import User, Post, JobTitle, EmploymentTerms


class UserSettingsForm(forms.ModelForm):
    # Existing user fields
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    date_of_birth = forms.DateField(required=False)
    gender = forms.CharField(required=False)
    address = forms.CharField(required=False)
    cityId = forms.CharField(required=False)

    # Modified employment start and end to be read-only
    employement_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )
    employement_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )

    profile_picture = forms.ImageField(required=False)
    job_title = forms.ModelChoiceField(
        queryset=JobTitle.objects.all(),
        empty_label=None,
        required=True
    )

    # Modified employment fields to be read-only
    agreed_salary = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'step': '0.01',
            'min': '0',
            'class': 'form-control',
            'placeholder': 'Enter agreed salary',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )
    salary_start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )
    salary_end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'readonly': 'readonly',
            'disabled': 'disabled'
        })
    )

    class Meta:
        model = User
        fields = [
            'email',
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'address',
            'cityId',
            'employement_start',
            'employement_end',
            'profile_picture',
            'job_title',
        ]
        exclude = ['password']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the user has employment terms, populate the fields
        if self.instance and self.instance.pk:
            try:
                employment_terms = EmploymentTerms.objects.filter(
                    employee=self.instance
                ).latest('salary_start_date')
                self.fields['agreed_salary'].initial = employment_terms.agreed_salary
                self.fields['salary_start_date'].initial = employment_terms.salary_start_date
                self.fields['salary_end_date'].initial = employment_terms.salary_end_date

                # Ensure these fields are read-only
                self.fields['agreed_salary'].widget.attrs['readonly'] = True
                self.fields['agreed_salary'].widget.attrs['disabled'] = True
                self.fields['salary_start_date'].widget.attrs['readonly'] = True
                self.fields['salary_start_date'].widget.attrs['disabled'] = True
                self.fields['salary_end_date'].widget.attrs['readonly'] = True
                self.fields['salary_end_date'].widget.attrs['disabled'] = True

                # Make employment start and end read-only
                self.fields['employement_start'].widget.attrs['readonly'] = True
                self.fields['employement_start'].widget.attrs['disabled'] = True
                self.fields['employement_end'].widget.attrs['readonly'] = True
                self.fields['employement_end'].widget.attrs['disabled'] = True
            except EmploymentTerms.DoesNotExist:
                pass

        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError('Email is already in use.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)
        return user


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']