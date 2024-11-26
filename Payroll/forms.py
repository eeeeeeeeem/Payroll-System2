from datetime import date

from django import forms
from Payroll.models import User, Post, JobTitle, EmploymentTerms, SalaryPayment, SalarySlipRequest


class UserSettingsForm(forms.ModelForm):
    # Existing user fields
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    date_of_birth = forms.DateField(required=False)
    gender = forms.CharField(required=False)
    address = forms.CharField(required=False)
    cityId = forms.CharField(required=False)

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

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
        }),
        required=True,
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
            'password'
        ]


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
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])  # Hash the password
        if commit:
            user.save()
        return user


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content', 'image']

from django import forms
from Payroll.models import Department, DepartmentHistory

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['department_name']

class DepartmentHistoryForm(forms.ModelForm):
    class Meta:
        model = DepartmentHistory
        fields = ['department', 'employee', 'start_date', 'end_date']

class SalaryPaymentForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.filter(role='EMPLOYEE'),
        label="Employee",
        widget=forms.Select(attrs={'class': 'form-control', 'required': 'true'})
    )
    base_salary = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'required': 'true'}),
        label="Base Salary"
    )
    bonus = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0.00,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Bonus"
    )
    deduction = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=0.00,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Deduction"
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date', 'required': 'true'}),
        label="Payment Date"
    )

    class Meta:
        model = SalaryPayment
        fields = ['user', 'base_salary', 'bonus', 'deduction', 'payment_date']


class SalarySlipRequestForm(forms.ModelForm):
    month = forms.DateField(widget=forms.HiddenInput())  # We'll set this via the month/year selections
    selected_month = forms.ChoiceField(
        choices=[(i, date(2000, i, 1).strftime('%B')) for i in range(1, 13)],
        label="Month"
    )
    selected_year = forms.ChoiceField(label="Year")
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Notes (Optional)"
    )

    class Meta:
        model = SalarySlipRequest
        fields = ['notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set up year choices
        current_year = date.today().year
        self.fields['selected_year'].choices = [
            (year, str(year)) for year in range(current_year - 2, current_year + 1)
        ]


