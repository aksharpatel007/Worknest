from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    # Base Profile
    fullname = models.CharField(max_length=255, null=True, blank=True)
    phone = models.CharField(max_length=15, null=True, blank=True)
    role_id = models.IntegerField(default=3) # 1:Admin, 2:Worker, 3:User
    profile_pic = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
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
    verification_date = models.DateTimeField(null=True, blank=True)

class Booking(models.Model):
    # Use related_names that match your views logic
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_as_client')
    worker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_as_worker')
    service_desc = models.TextField()
    status = models.CharField(max_length=20, default='pending')
    # Renamed to created_at to match your view sorting logic
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.client.fullname} hired {self.worker.fullname}"