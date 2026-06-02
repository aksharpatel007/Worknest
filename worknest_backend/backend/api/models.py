from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    # Base Profile
    fullname = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    role_id = models.IntegerField(default=3) # 1:Admin, 2:Worker, 3:User
    profile_pic = models.ImageField(upload_to='profiles/', null=True, blank=True)
    session_key = models.CharField(max_length=255, null=True, blank=True)
    date_joined = models.DateTimeField(default=timezone.now())
    
    # Worker Specific Fields
    skill = models.CharField(max_length=100, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    # Changed to Integer for easier calculation in views
    hourly_rate = models.IntegerField(default=0)
    worker_status = models.CharField(max_length=20, default='newbie')

    # Map & Rating Data
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_jobs = models.IntegerField(default=0)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Verification System
    is_verified = models.BooleanField(default=False)
    id_proof_image = models.ImageField(upload_to='id_proofs/', null=True, blank=True)
    trust_score = models.IntegerField(default=0)
    is_fraud = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)

class Booking(models.Model):
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_bookings')
    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='worker_jobs')
    service_desc = models.TextField()
    status = models.CharField(max_length=20, default='pending') # pending, accepted, in_progress, completed
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Time Tracking Parameters
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Dynamic Financial Configuration
    hourly_rate_snapshot = models.IntegerField(default=0)
    final_price = models.IntegerField(default=0)
    
    # Consumer Feedback Fields
    rating_given = models.IntegerField(null=True, blank=True) # 1 to 5 Stars
    review_given = models.TextField(null=True, blank=True)

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    booking_reference = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)