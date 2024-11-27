from django.shortcuts import redirect
from django.urls import resolve
from django.contrib import messages


class RoleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # URLs that only HR can access
        hr_urls = [
            'manage_employees',
            'salary_payment_create',
            'salary_payment_list',
            'department_create',
            'employment_terms_register',
        ]

        try:
            url_name = resolve(request.path_info).url_name

            if url_name in hr_urls and not request.user.is_hr():
                messages.error(request, 'Access denied. HR privileges required.')
                return redirect('dashboard')

        except:
            pass

        response = self.get_response(request)
        return response