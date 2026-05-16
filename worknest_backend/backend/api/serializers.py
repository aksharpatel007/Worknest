from rest_framework import serializers
from .models import User, Booking

# Ensure is_verified is in your fields list
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'fullname', 'email', 'role_id', 'is_verified', 'is_fraud', 
            'profile_pic', 'skill', 'hourly_rate', 'rating', 'total_jobs', 
            'date_joined', 'id_proof_image', 'phone', 'bio'
        ]
        
class BookingSerializer(serializers.ModelSerializer):
    worker_name = serializers.ReadOnlyField(source='worker.fullname')
    client_name = serializers.ReadOnlyField(source='client.fullname')
    class Meta:
        model = Booking
        fields = '__all__'