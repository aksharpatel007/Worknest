from django.urls import path
from . import views
from django.conf import settings # Add this import
from django.conf.urls.static import static # Add this import

urlpatterns = [
    # Auth & Signup
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_api, name='change_password_api'),
    path('forgot-password/', views.forgot_password_api, name='forgot_password_api'),
    
    
    # Profile & Worker Listing
    path('profile/', views.profile_view, name='profile'),
    path('workers/', views.worker_list, name='worker-list'),
    path('workers/<int:worker_id>/', views.worker_detail_api, name='worker-detail'),
    
    
    # Bookings
    path('bookings/', views.user_bookings, name='user-bookings'),
    path('bookings/<int:booking_id>/', views.user_bookings, name='booking-detail'),
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
    path('categories/', views.category_list, name='category-list'),
]

# Add this block at the very bottom!
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)