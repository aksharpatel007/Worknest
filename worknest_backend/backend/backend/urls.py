"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""


from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from api import views  

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),

    # HTML Page Views
    path('', views.index_page, name='index_page'),
    
    # User Pages
    path('login/', views.login_page, name='login_page'),
    path('signup/', views.signup_page, name='signup_page'),
    path('forgot-password/', views.forgot_password_page, name='forgot_password_page'),
    path('change-password/', views.change_password_page, name='change_password_page'),
    path('dashboard/', views.dashboard_page, name='dashboard_page'),
    path('profile/', views.profile_page, name='profile_page'),
    path('services/', views.services_page, name='services_page'),
    path('worker-list/', views.worker_list_page, name='worker_list_page'),
    path('worker-detail/', views.worker_detail_page, name='worker_detail_page'),
    path('booking-request/', views.booking_request_page, name='booking_request_page'),
    path('booking-history/', views.booking_history_page, name='booking_history_page'),
    path('map/', views.map_page, name='map_page'),
    path('messages/', views.user_messages_page, name='user_messages_page'),

    # Worker Pages
    path('worker/signup/', views.worker_signup_page, name='worker_signup_page'),
    path('worker/dashboard/', views.worker_dashboard_page, name='worker_dashboard_page'),
    path('worker/profile/', views.worker_profile_page, name='worker_profile_page'),
    path('worker/booking-history/', views.worker_booking_history_page, name='worker_booking_history_page'),
    path('worker/requests/', views.worker_requests_page, name='worker_requests_page'),
    path('worker/messages/', views.worker_messages_page, name='worker_messages_page'),
    path('worker/search/', views.worker_search_page, name='worker_search_page'),
    path('worker/detail/', views.worker_detail_page_worker, name='worker_detail_page_worker'),
    path('worker/change-password/', views.worker_change_password_page, name='worker_change_password_page'),

    # Admin Pages
    path('admin-dashboard/', views.admin_dashboard_page, name='admin_dashboard_page'),
    path('admin-users/', views.admin_users_page, name='admin_users_page'),
    path('admin-verify/', views.admin_verify_page, name='admin_verify_page'),
    path('admin-booking/', views.admin_booking_page, name='admin_booking_page'),
    path('admin-fraud/', views.admin_fraud_page, name='admin_fraud_page'),
    path('admin-settings/', views.admin_settings_page, name='admin_settings_page'),
]

# --- CRITICAL FOR SHOWING ID PROOFS & PROFILE PICS ---
# This allows the browser to access files in your 'media' folder
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
