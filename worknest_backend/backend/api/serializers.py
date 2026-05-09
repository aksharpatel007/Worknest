from rest_framework import serializers
from .models import User, Booking

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'fullname', 'email', 'phone', 'role_id', 'profile_pic', 'skill', 'bio', 'hourly_rate', 'worker_status', 'rating', 'total_jobs', 'latitude', 'longitude']

class BookingSerializer(serializers.ModelSerializer):
    worker_name = serializers.ReadOnlyField(source='worker.fullname')
    client_name = serializers.ReadOnlyField(source='client.fullname')
    class Meta:
        model = Booking
        fields = '__all__'