from rest_framework import serializers
from .models import User, Booking , Notification

# Ensure is_verified is in your fields list
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'fullname', 'email', 'role_id', 'is_verified', 'is_fraud', 
            'profile_pic', 'skill', 'hourly_rate', 'rating', 'total_jobs', 
            'date_joined', 'id_proof_image', 'phone', 'bio', 'admin_messages', 'worker_status', 'latitude', 'longitude', 'trust_score'
        ]
        
class BookingSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.fullname', read_only=True)
    worker_name = serializers.CharField(source='worker.fullname', read_only=True)
    worker_skill = serializers.CharField(source='worker.skill', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    worker_email = serializers.CharField(source='worker.email', read_only=True)
    client_avatar = serializers.ImageField(source='client.profile_pic', read_only=True)
    worker_avatar = serializers.ImageField(source='worker.profile_pic', read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id', 'client', 'worker', 'client_name', 'worker_name', 'worker_skill',
            'client_email', 'worker_email', 'client_avatar', 'worker_avatar', 'service_desc', 'status', 
            'created_at', 'started_at', 'completed_at', 
            'hourly_rate_snapshot', 'final_price', 'rating_given', 'review_given'
        ]

class NotificationSerializer(serializers.ModelSerializer):
    formatted_date = serializers.DateTimeField(source='created_at', format="%d %b %Y, %I:%M %p", read_only=True)
    
    class Meta:
        model = Notification
        fields = ['id', 'user', 'title', 'message', 'booking_reference', 'created_at', 'formatted_date', 'is_read']