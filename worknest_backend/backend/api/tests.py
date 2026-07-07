from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from api.models import Booking
import math

User = get_user_model()

class BookingRateCalculationTestCase(TestCase):
    def setUp(self):
        # Create users
        self.client_user = User.objects.create_user(
            username='client@example.com',
            email='client@example.com',
            password='password123',
            fullname='Client User',
            role_id=3,
            session_key='client-token'
        )
        self.worker = User.objects.create_user(
            username='worker@example.com',
            email='worker@example.com',
            password='password123',
            fullname='Worker Specialist',
            role_id=2,
            hourly_rate=400,
            is_verified=True,
            session_key='worker-token'
        )

    def test_booking_time_spent_calculation(self):
        # Create pending booking
        booking = Booking.objects.create(
            client=self.client_user,
            worker=self.worker,
            service_desc='Fixing faucet',
            status='pending',
            hourly_rate_snapshot=self.worker.hourly_rate
        )
        
        self.assertIsNone(booking.started_at)
        
        # Simulating accepting booking via PATCH endpoint logic
        booking.status = 'accepted'
        booking.started_at = timezone.now()
        booking.save()
        
        self.assertIsNotNone(booking.started_at)
        
        # Set exact started_at and completed_at to simulate 1.5 hours spent
        now = timezone.now()
        booking.started_at = now - timezone.timedelta(hours=1.5)
        booking.completed_at = now
        booking.status = 'completed'
        
        duration = booking.completed_at - booking.started_at
        hours_consumed = max(0.0, duration.total_seconds() / 3600.0)
        
        # Pro-rated exact calculation
        booking.final_price = math.ceil(hours_consumed * booking.hourly_rate_snapshot)
        booking.save()
        
        expected_price = math.ceil(1.5 * 400) # 1.5 * 400 = 600
        self.assertEqual(booking.final_price, expected_price)
        self.assertEqual(booking.final_price, 600)
        
        # Test with very short duration (e.g. 15 minutes)
        booking2 = Booking.objects.create(
            client=self.client_user,
            worker=self.worker,
            service_desc='Another task',
            status='accepted',
            hourly_rate_snapshot=self.worker.hourly_rate
        )
        booking2.started_at = now - timezone.timedelta(minutes=15)
        booking2.completed_at = now
        booking2.status = 'completed'
        
        duration2 = booking2.completed_at - booking2.started_at
        hours_consumed2 = max(0.0, duration2.total_seconds() / 3600.0)
        booking2.final_price = math.ceil(hours_consumed2 * booking2.hourly_rate_snapshot)
        booking2.save()
        
        expected_price2 = math.ceil((15.0 / 60.0) * 400) # 100
        self.assertEqual(booking2.final_price, expected_price2)
        self.assertEqual(booking2.final_price, 100)

    def test_booking_patch_api_accepted_and_completed(self):
        # Create a pending booking
        booking = Booking.objects.create(
            client=self.client_user,
            worker=self.worker,
            service_desc='Garden Cleanup',
            status='pending',
            hourly_rate_snapshot=200
        )
        
        # 1. Patch status to 'accepted' using worker's session key
        url = reverse('user-bookings')
        headers = {'HTTP_X_SESSION_KEY': 'worker-token'}
        
        response = self.client.patch(
            url,
            data={'booking_id': booking.id, 'status': 'accepted'},
            content_type='application/json',
            **headers
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # Verify started_at is now set on the booking
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'accepted')
        self.assertIsNotNone(booking.started_at)
        
        # Mock started_at to 30 minutes ago
        now = timezone.now()
        booking.started_at = now - timezone.timedelta(minutes=30)
        booking.save()
        
        # 2. Patch status to 'completed' using client's session key
        headers_client = {'HTTP_X_SESSION_KEY': 'client-token'}
        response_completed = self.client.patch(
            url,
            data={'booking_id': booking.id, 'status': 'completed'},
            content_type='application/json',
            **headers_client
        )
        
        self.assertEqual(response_completed.status_code, 200)
        self.assertEqual(response_completed.json()['status'], 'success')
        
        # Verify final price is exactly 100 (30 mins of 200/hr)
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
        self.assertIsNotNone(booking.completed_at)
        
        # Difference should be roughly 30 minutes, final price should be ceil(0.5 * 200) = 100
        self.assertAlmostEqual(booking.final_price, 100, delta=2)
        
        # Verify dashboard stats for the worker calculates the correct earnings
        url_stats = reverse('dashboard-stats')
        response_stats = self.client.get(
            url_stats,
            **headers
        )
        self.assertEqual(response_stats.status_code, 200)
        self.assertAlmostEqual(response_stats.json()['data']['earnings'], 100, delta=2)

    def test_send_verification_message(self):
        # Create unverified user who signed up as client (role_id=3)
        unverified_user = User.objects.create_user(
            username='unverified@example.com',
            email='unverified@example.com',
            password='password123',
            fullname='Unverified Goyal',
            role_id=3,
            is_verified=False,
            session_key='unverified-token'
        )
        
        url = reverse('profile')
        headers = {'HTTP_X_SESSION_KEY': 'unverified-token'}
        
        response = self.client.post(
            url,
            data={'bio': 'VERIFICATION_NOTE: [6 Jul 2026, 11:53 am] Please approve me'},
            content_type='application/json',
            **headers
        )
        
        self.assertEqual(response.status_code, 200)
        
        unverified_user.refresh_from_db()
        self.assertEqual(unverified_user.admin_messages, 'VERIFICATION_NOTE: [6 Jul 2026, 11:53 am] Please approve me')
        self.assertIsNone(unverified_user.bio) # bio should not be modified
        self.assertEqual(unverified_user.role_id, 2) # should automatically be converted to role_id=2 (Worker)
