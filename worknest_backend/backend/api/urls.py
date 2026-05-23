from django.urls import path
from . import views

urlpatterns = [
    # Auth & Signup
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    
    # Profile & Worker Listing
    path('profile/', views.profile_view, name='profile'),
    path('workers/', views.worker_list, name='worker-list'),
    
    # Bookings
    # path('bookings/create/', views.create_booking, name='create-booking'),
    path('bookings/', views.user_bookings, name='user-bookings'),
    path('bookings/rate/', views.submit_rating, name='submit-rating'),
    path('notifications/', views.get_user_notifications, name='user-notifications'),
    
    # Dashboard Stats
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
    
    # Admin Actions
    path('admin/unverified/', views.get_unverified_workers, name='admin-unverified'),
    path('admin/verify/<int:worker_id>/', views.verify_worker, name='admin-verify'),
    path('admin/stats/', views.get_admin_stats, name='admin-stats'),
    path('admin/users/', views.get_all_users, name='admin-all-users'),
    path('admin/bookings/', views.get_all_bookings, name='admin-all-bookings'),
    path('admin/fraud/<int:worker_id>/', views.flag_fraud, name='flag_fraud'),
]