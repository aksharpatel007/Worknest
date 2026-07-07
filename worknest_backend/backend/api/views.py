from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate,login
from django.db.models import Avg, Q
from django.http import JsonResponse
import math
import uuid
import json
from django.utils import timezone
from .models import User, Booking, Notification
from .serializers import UserSerializer, BookingSerializer, NotificationSerializer
from rest_framework.permissions import AllowAny
from rest_framework.decorators import authentication_classes, permission_classes
from django.contrib.auth import get_user_model 


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371.0  # Radius of Earth in km
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@csrf_exempt
@api_view(['GET'])
def category_list(request):
    """Fetches all unique skills/categories from verified workers in the database."""
    skills = User.objects.filter(role_id=2, is_verified=True, is_fraud=False, skill__isnull=False).exclude(skill='').values_list('skill', flat=True).distinct()
    return Response({'status': 'success', 'data': list(skills)}, status=200)

# --- AUTHENTICATION & SIGNUP ---

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def signup_view(request):
    """
    Consolidated signup that handles personal details, professional skills, 
    and ID proof upload in one request.
    """
    try:
        data = request.data
        if User.objects.filter(email=data['email']).exists():
            return Response({'status': 'error', 'message': 'Email already registered'}, status=400)
        
        # Create user with all professional fields integrated
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            fullname=data['fullname'],
            phone=data.get('phone', ''),
            skill=data.get('skill', ''),
            hourly_rate=data.get('hourly_rate', 0),
            bio=data.get('bio', ''),
            role_id=data.get('role_id', 3),
            is_verified=False  # New workers start as unverified for fraud protection
        )

        # After User.objects.create_user...
        if 'id_proof_image' in request.FILES:
            user.id_proof_image = request.FILES['id_proof_image']
            user.save()

        return Response({'status': 'success', 'message': 'Account created! Admin will verify your ID.'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)

from django.contrib.auth import login

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """Authenticates a user, saves their tracking token to the DB, and logs them in."""
    email = request.data.get('email')
    password = request.data.get('password')
    
    # Support login using either username or email
    username_to_auth = email
    try:
        user_obj = User.objects.get(Q(username__iexact=email) | Q(email__iexact=email))
        username_to_auth = user_obj.username
    except User.DoesNotExist:
        pass
        
    user = authenticate(username=username_to_auth, password=password)
    
    if user:
        login(request, user)  # Sets native Django cookies
        
        # 🎯 FIX 1: Generate a unique session key and save it to this specific user row!
        key = str(uuid.uuid4())
        user.session_key = key
        user.save()
        
        # Route roles smoothly
        if user.role_id == 1:
            redirect_page = '/admin-dashboard/'
        elif user.role_id == 2:
            redirect_page = '/worker/dashboard/'
        else:
            redirect_page = '/dashboard/'
        
        return Response({
            'status': 'success',
            'session_key': key,
            'redirect': redirect_page
        }, status=200)
        
    return Response({'status': 'error', 'message': 'Invalid login credentials.'}, status=401)


from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    """Logs out the user and redirects to the landing page."""
    # Invalidate user session key if possible
    try:
        user = get_authenticated_user_from_header(request)
        if not user and request.user.is_authenticated:
            user = request.user
        if user:
            user.session_key = None
            user.save()
    except Exception:
        pass
    logout(request)
    return redirect('/')


# 🎯 CHANGE PASSWORD API
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def change_password_api(request):
    """
    Safely checks the current password and updates it with a new one 
    using the custom X-Session-Key header validation.
    """
    if request.method == 'POST':
        # તમારા સેશન કી ના હેડર લોજિકથી એક્ટિવ યુઝરને શોધો
        user = get_authenticated_user_from_header(request)
        
        if not user:
            return Response({'status': 'error', 'message': 'User session expired or invalid. Please log in again.'}, status=401)
            
        try:
            current_password = request.data.get('current_password')
            new_password = request.data.get('new_password')
            
            if not user.check_password(current_password):
                return Response({'status': 'error', 'message': 'Current password is incorrect!'}, status=400)
                
            user.set_password(new_password)
            user.save()
            
            return Response({'status': 'success', 'message': 'Password updated successfully!'})
            
        except Exception as e:
            return Response({'status': 'error', 'message': f'Server Error: {str(e)}'}, status=500)


# --- PROFILE & WORKER LISTS ---

@csrf_exempt
@api_view(['GET'])
def worker_list(request):
    """Fetches all online, verified, non-fraud workers, optionally filtered by skill and sorted by distance."""
    user = get_authenticated_user_from_header(request)
    ref_lat = None
    ref_lon = None
    
    # 1. Check query parameters
    lat_param = request.query_params.get('latitude')
    lon_param = request.query_params.get('longitude')
    if lat_param and lon_param:
        try:
            ref_lat = float(lat_param)
            ref_lon = float(lon_param)
        except ValueError:
            pass
            
    # 2. Check authenticated user's profile location
    if (ref_lat is None or ref_lon is None) and user:
        if user.latitude is not None and user.longitude is not None:
            ref_lat = float(user.latitude)
            ref_lon = float(user.longitude)
            
    # Fallback Ahmedabad coords
    fallback_used = False
    if ref_lat is None or ref_lon is None:
        ref_lat = 23.0225
        ref_lon = 72.5714
        fallback_used = True

    # Filter online, verified, non-fraud workers
    workers = User.objects.filter(
        role_id=2, 
        is_verified=True, 
        is_fraud=False, 
        worker_status__in=['online', 'verified']
    )
    
    # Optional category filter
    skill = request.query_params.get('skill')
    if skill:
        workers = workers.filter(skill__iexact=skill)
        
    data_list = []
    for worker in workers:
        lat = worker.latitude
        lon = worker.longitude
        
        # Seed coordinates if null
        if lat is None or lon is None:
            import hashlib
            h = int(hashlib.md5(str(worker.id).encode()).hexdigest(), 16)
            lat_offset = ((h % 1000) / 1000.0 - 0.5) * 0.04
            lon_offset = (((h // 1000) % 1000) / 1000.0 - 0.5) * 0.04
            lat = ref_lat + lat_offset
            lon = ref_lon + lon_offset
        else:
            lat = float(lat)
            lon = float(lon)
            
        dist = haversine_distance(ref_lat, ref_lon, lat, lon)
        is_available = not Booking.objects.filter(worker=worker, status='in_progress').exists()
        
        data_list.append({
            'id': worker.id,
            'fullname': worker.fullname,
            'username': worker.username,
            'email': worker.email,
            'skill': worker.skill or 'Artisan',
            'hourly_rate': worker.hourly_rate,
            'bio': getattr(worker, 'bio', ''),
            'rating': float(worker.rating) if worker.rating else 0.0,
            'total_jobs': getattr(worker, 'total_jobs', 0),
            'submitted_at': worker.date_joined.strftime('%I:%M %p') if worker.date_joined else 'N/A',
            'latitude': lat,
            'longitude': lon,
            'profile_pic': worker.profile_pic.url if worker.profile_pic else None,
            'is_verified': worker.is_verified,
            'is_fraud': worker.is_fraud,
            'worker_status': worker.worker_status,
            'is_available': is_available,
            'distance': dist,
            'distance_text': f"{round(dist, 1)} km" if not fallback_used else "Nearby"
        })
        
    data_list.sort(key=lambda w: w['distance'])
        
    return Response({'status': 'success', 'data': data_list}, status=200)


@csrf_exempt
@api_view(['GET', 'POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def profile_view(request):
    user = get_authenticated_user_from_header(request) 
    if not user:
        return Response({'status': 'error', 'message': 'Invalid session'}, status=401) 

    if request.method == 'GET':
        completed_bookings = Booking.objects.filter(worker=user, status='completed')
        earnings = sum(b.final_price for b in completed_bookings)
        return Response({
            'status': 'success',
            'data': {
                'id': user.id,
                'username': user.username,
                'fullname': user.fullname,
                'email': user.email,
                'phone': user.phone,
                'role_id': user.role_id,
                'skill': user.skill,
                'bio': user.bio, 
                'admin_messages': user.admin_messages, 
                'hourly_rate': user.hourly_rate,
                'is_verified': user.is_verified,
                'is_fraud': user.is_fraud,
                'profile_pic': user.profile_pic.url if user.profile_pic else None,
                'created_at': user.date_joined.isoformat() if user.date_joined else None,
                'date_joined': user.date_joined.isoformat() if user.date_joined else None,
                'rating': float(user.rating) if user.rating else 0.0,
                'total_jobs': user.total_jobs,
                'earnings': earnings,
                'worker_status': user.worker_status,
                'latitude': float(user.latitude) if user.latitude is not None else None,
                'longitude': float(user.longitude) if user.longitude is not None else None,
                'trust_score': user.trust_score
            }
        })
    elif request.method == 'POST':
        data = request.data
        
        if 'fullname' in data: user.fullname = data['fullname'] 
        if 'phone' in data: user.phone = data['phone'] 
        if 'hourly_rate' in data: user.hourly_rate = data['hourly_rate']
        if 'skill' in data: user.skill = data['skill']
        if 'worker_status' in data: user.worker_status = data['worker_status']
        if 'latitude' in data: user.latitude = data['latitude']
        if 'longitude' in data: user.longitude = data['longitude']
        
        # 🎯 CHANNELS MODULAR ROUTING: Separates verification streams from clean text bios instantly
        if 'bio' in data:
            incoming_text = data['bio'] 
            if "VERIFICATION_NOTE:" in incoming_text or "APPEAL_REQUEST:" in incoming_text:
                user.admin_messages = f"{user.admin_messages or ''}\n{incoming_text}".strip()
                user.role_id = 2  # Automatically convert/ensure role is Worker when applying for verification
            else:
                user.bio = incoming_text 
                
        if 'profile_pic' in request.FILES: user.profile_pic = request.FILES['profile_pic']
            
        user.save() 
        return Response({'status': 'success', 'message': 'Profile updated successfully.'})
    

from django.utils import timezone
import math

@csrf_exempt
@api_view(['GET', 'POST', 'PATCH'])
@authentication_classes([])
@permission_classes([AllowAny])
def user_bookings(request):
    user = get_authenticated_user_from_header(request)
    
    # ------------------ GET: LISTING LEDGERS ------------------
    if request.method == 'GET':
        if not user:
            return Response({'status': 'success', 'data': []}, status=200)
        
        if user.role_id == 2:
            bookings = Booking.objects.filter(worker=user).order_by('-id')
        else:
            bookings = Booking.objects.filter(client=user).order_by('-id')
            
        serializer = BookingSerializer(bookings, many=True)
        
        # 🎯 ADDITION: Inject formatted dates and security-wrapped locations
        custom_data = []
        for b, serialized_item in zip(bookings, serializer.data):
            item_dict = dict(serialized_item)
            item_dict['formatted_date'] = b.created_at.strftime('%d %b %Y') if b.created_at else 'Recent'
            
            # Inject client & worker phone numbers
            item_dict['client_phone'] = b.client.phone or '+91 98765 43210'
            item_dict['worker_phone'] = b.worker.phone or '+91 98765 43210'
            
            if b.status in ['accepted', 'in_progress']:
                c_lat = float(b.client.latitude) if b.client.latitude is not None else 23.0225
                c_lon = float(b.client.longitude) if b.client.longitude is not None else 72.5714
                
                w_lat = b.worker.latitude
                w_lon = b.worker.longitude
                if w_lat is None or w_lon is None:
                    import hashlib
                    h = int(hashlib.md5(str(b.worker.id).encode()).hexdigest(), 16)
                    lat_offset = ((h % 1000) / 1000.0 - 0.5) * 0.04
                    lon_offset = (((h // 1000) % 1000) / 1000.0 - 0.5) * 0.04
                    w_lat = c_lat + lat_offset
                    w_lon = c_lon + lon_offset
                else:
                    w_lat = float(w_lat)
                    w_lon = float(w_lon)
                    
                item_dict['client_latitude'] = c_lat
                item_dict['client_longitude'] = c_lon
                item_dict['worker_latitude'] = w_lat
                item_dict['worker_longitude'] = w_lon
            else:
                item_dict['client_latitude'] = None
                item_dict['client_longitude'] = None
                item_dict['worker_latitude'] = None
                item_dict['worker_longitude'] = None
                
            # Include approximate distance
            if b.client.latitude is not None and b.client.longitude is not None and b.worker.latitude is not None and b.worker.longitude is not None:
                dist = haversine_distance(
                    float(b.client.latitude), float(b.client.longitude),
                    float(b.worker.latitude), float(b.worker.longitude)
                )
                item_dict['approximate_distance'] = f"~{round(dist, 1)} km"
            else:
                # Seed approximate distance if coordinates are null
                import hashlib
                h = int(hashlib.md5(str(b.id).encode()).hexdigest(), 16)
                approx_dist = 1.0 + (h % 50) / 10.0  # 1.0 to 6.0 km
                item_dict['approximate_distance'] = f"~{round(approx_dist, 1)} km"
                
            custom_data.append(item_dict)
            
        return Response({'status': 'success', 'data': custom_data}, status=200)
    
    # ------------------ POST: DISPATCH INITIAL JOB ------------------
    elif request.method == 'POST':
        try:
            worker_id = int(request.data.get('worker_id'))
            client_id = int(request.data.get('client_id'))
            service_desc = request.data.get('service_desc')

            client = User.objects.get(id=client_id)
            worker = User.objects.get(id=worker_id)

            # Enforce Online/Offline verification (Phase 1)
            if worker.worker_status not in ['online', 'verified']:
                return Response({'status': 'error', 'message': 'This worker is currently unavailable.'}, status=400)

            booking = Booking.objects.create(
                client=client,
                worker=worker,
                service_desc=service_desc,
                status='pending',
                hourly_rate_snapshot=getattr(worker, 'hourly_rate', 400)
            )
            
            # Dispatch Alert to the Worker Inbox that a job is pending
            Notification.objects.create(
                user=worker,
                title="New Booking Request Received",
                message=f"Client {client.fullname} has sent an assignment request for: '{service_desc[:40]}...'",
                booking_reference=booking
            )
            
            return Response({'status': 'success', 'booking_id': booking.id}, status=201)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

    # ------------------ PATCH: STATE TRANSITIONS & TIME LOGS ------------------
    elif request.method == 'PATCH':
        try:
            booking_id = request.data.get('booking_id')
            new_status = request.data.get('status')
            booking = Booking.objects.get(id=booking_id)
            
            if new_status == 'in_progress':
                booking.started_at = timezone.now()
                booking.status = 'in_progress'
                
                Notification.objects.create(
                    user=booking.client,
                    title="Job Started",
                    message=f"Artisan specialist {booking.worker.fullname} has officially clocked in and started working on your request.",
                    booking_reference=booking
                )
                
            elif new_status == 'completed':
                if not booking.started_at:
                    booking.started_at = timezone.now() - timezone.timedelta(hours=1) # Fallback if worker forgot to click start
                
                booking.completed_at = timezone.now()
                booking.status = 'completed'
                
                # Compute Exact Elapsed Time Consumed
                duration = booking.completed_at - booking.started_at
                hours_consumed = max(0.0, duration.total_seconds() / 3600.0)
                
                # Format time string for descriptive message outputs
                seconds_total = int(duration.total_seconds())
                mins_total = seconds_total // 60
                hrs_part = mins_total // 60
                mins_part = mins_total % 60
                
                if hrs_part > 0:
                    time_str = f"{hrs_part} hrs {mins_part} mins"
                elif mins_total > 0:
                    time_str = f"{mins_total} mins"
                else:
                    time_str = f"{seconds_total} seconds"
                
                booking.final_price = math.ceil(hours_consumed * booking.hourly_rate_snapshot)
                booking.save()
                
                # Build rich description summary text layout
                summary_msg = (
                    f"Receipt Confirmation Layout:\n"
                    f"• Job Reference ID: #{booking.id}\n"
                    f"• Client Owner: {booking.client.fullname}\n"
                    f"• Service Provider: {booking.worker.fullname} ({booking.worker.skill})\n"
                    f"• Scheduled Clock In: {booking.started_at.strftime('%d %b, %I:%M %p')}\n"
                    f"• Completion Stamp: {booking.completed_at.strftime('%d %b, %I:%M %p')}\n"
                    f"• Total Time Consumed: {time_str}\n"
                    f"• Rate Snapshot Applied: ₹{booking.hourly_rate_snapshot}/hr\n"
                    f"• Absolute Total Billing Amount: ₹{booking.final_price}"
                )
                
                # Inject real-time summary notification cards into BOTH users' feeds
                Notification.objects.create(user=booking.client, title="Work Complete — Receipt Details", message=summary_msg, booking_reference=booking)
                Notification.objects.create(user=booking.worker, title="Work Complete — Earning Summary", message=summary_msg, booking_reference=booking)
                
            else:
                booking.status = new_status
                if new_status == 'accepted':
                    booking.started_at = timezone.now()
                    # Find duplicate pending bookings by the same client with the same service description
                    duplicate_bookings = Booking.objects.filter(
                        client=booking.client,
                        service_desc=booking.service_desc,
                        status='pending'
                    ).exclude(id=booking.id)
                    # Delete notifications for duplicate bookings
                    Notification.objects.filter(booking_reference__in=duplicate_bookings).delete()
                    # Delete the duplicate bookings
                    duplicate_bookings.delete()
                
            booking.save()
            return Response({'status': 'success', 'message': f'State moved to {new_status}'}, status=200)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def submit_rating(request):
    """Handles client reviews and updates the worker's average rating dynamically."""
    try:
        booking_id = int(request.data.get('booking_id'))
        rating_value = int(request.data.get('rating')) # 1 to 5
        review_text = request.data.get('review', '')
        
        booking = Booking.objects.get(id=booking_id)
        booking.rating_given = rating_value
        booking.review_given = review_text
        booking.save()
        
        # Recalculate Global Worker Metrics Snapshot values
        worker = booking.worker
        all_completed_jobs = Booking.objects.filter(worker=worker, status='completed')
        
        worker.total_jobs = all_completed_jobs.count()
        avg_calc = all_completed_jobs.filter(rating_given__isnull=False).aggregate(Avg('rating_given'))['rating_given__avg']
        worker.rating = round(avg_calc, 1) if avg_calc else float(rating_value)
        worker.save()
        
        return Response({'status': 'success', 'message': 'Rating saved successfully and added to worker profile totals!'})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@api_view(['GET'])
def get_user_notifications(request):
    """Fetches user-specific notification logs explicitly pre-sorted by newest date and time."""
    user = get_authenticated_user_from_header(request)
    if not user:
        return Response({'status': 'error', 'message': 'Session authentication invalid'}, status=401)
    
    # 🎯 FIX: Order explicitly by '-created_at' and '-id' so the database forces newest items to the top
    notifications = Notification.objects.filter(user=user).order_by('-created_at', '-id')
    serializer = NotificationSerializer(notifications, many=True)
    return Response({'status': 'success', 'data': serializer.data}, status=200)


# ================== ADMIN PANEL QUERIES UPDATES ==================
@csrf_exempt
@api_view(['GET'])
def get_all_bookings(request):
    """Admin operational grid loading query."""
    bookings = Booking.objects.all().order_by('-id')
    serializer = BookingSerializer(bookings, many=True)
    return Response({'status': 'success', 'data': serializer.data})


@api_view(['GET'])
def dashboard_stats(request):
    """Calculates earnings and job counts for the worker dashboard."""
    user = request.user
    if not user.is_authenticated or user.role_id != 2:
        # Fetching latest worker for demo purposes if not logged in
        user = User.objects.filter(role_id=2).last()

    total_jobs = Booking.objects.filter(worker=user).count()
    pending_jobs = Booking.objects.filter(worker=user, status='pending').count()
    completed_jobs_query = Booking.objects.filter(worker=user, status='completed')
    completed_jobs = completed_jobs_query.count()
    earnings = sum(b.final_price for b in completed_jobs_query)
    
    return Response({
        'status': 'success',
        'data': {
            'total_jobs': total_jobs,
            'pending_jobs': pending_jobs,
            'earnings': earnings,
            'rating': getattr(user, 'rating', 0),
            'is_verified': user.is_verified # Used to show/hide dashboard banner
        }
    })

# --- ADMIN ACTIONS ---

@csrf_exempt
@api_view(['GET'])
def get_unverified_workers(request):
    """Fetches unverified workers using native, un-manipulated database properties."""
    unverified_workers = User.objects.filter(role_id=2, is_verified=False).order_by('-id') 
    
    data_list = []
    for worker in unverified_workers:
        data_list.append({
            'id': worker.id,
            'fullname': worker.fullname,
            'email': worker.email,
            'skill': worker.skill or 'Artisan',
            'hourly_rate': worker.hourly_rate,
            'bio': worker.bio or "No bio provided.",
            'admin_messages': worker.admin_messages or "",
            'admin_note': worker.admin_messages or "No messages sent to administration yet.",
            'submitted_at': worker.date_joined.strftime('%d %b %Y, %I:%M %p') if worker.date_joined else 'N/A'
        })
        
    return Response({'status': 'success', 'data': data_list}, status=200) 

@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_worker(request, worker_id):
    try:
        worker = User.objects.get(id=worker_id)
        
        # Check if the frontend requested a fraud flag instead of approval
        if request.data.get('action') == 'fraud':
            worker.is_fraud = True
            worker.is_verified = False
            worker.save()
            return Response({'status': 'success', 'message': 'Flagged successfully'})
            
        # Standard validation approval path
        worker.is_verified = True
        worker.is_fraud = False 
        worker.save()
        return Response({'status': 'success'})
    except User.DoesNotExist:
        return Response({'status': 'error'}, status=404)
        

@api_view(['GET'])
def get_admin_stats(request):
    """
    Calculates the counts for the Admin Dashboard stat cards.
    """
    # Count normal users (role_id 3)
    total_users = User.objects.filter(role_id=3).count()
    
    # Count all workers (role_id 2)
    total_workers = User.objects.filter(role_id=2).count()
    
    # Count every booking in the system
    total_bookings = Booking.objects.count()
    
    # Placeholder for fraud reports until the model is created
    open_reports = 0 

    return Response({
        'status': 'success',
        'data': {
            'total_users': total_users,
            'total_workers': total_workers,
            'total_bookings': total_bookings,
            'open_reports': open_reports
        }
    })


#
@api_view(['GET'])
def get_all_users(request):
    # This endpoint is used by admin_fraud.html to load the list
    users = User.objects.all()
    serializer = UserSerializer(users, many=True) # Must use the updated Serializer
    return Response({'status': 'success', 'data': serializer.data})



@csrf_exempt
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def update_report_status(request):
    """Admin action to suspend/verify workers via fraud panel"""
    report_id = request.data.get('report_id')
    new_status = request.data.get('status')
    
    # In a real app, you'd update a 'Report' model. 
    # For the demo, we can use this to flip the 'is_verified' flag
    return Response({'status': 'success', 'message': 'Worker status updated'})




@api_view(['GET'])
def get_fraud_reports(request):
    # Filter for workers with a trust score below 50% or explicit reports
    low_trust_workers = User.objects.filter(role_id=2, trust_score__lt=50)
    serializer = UserSerializer(low_trust_workers, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@csrf_exempt
@api_view(['GET'])
def worker_detail_api(request, worker_id):
    """Fetches details of a specific worker along with all user ratings/reviews."""
    try:
        worker = User.objects.get(id=worker_id, role_id=2)
    except User.DoesNotExist:
        return Response({'status': 'error', 'message': 'Worker not found'}, status=404)
        
    # Get all bookings for this worker that have reviews
    bookings = Booking.objects.filter(worker=worker, rating_given__isnull=False).order_by('-completed_at', '-id')
    
    reviews = []
    for b in bookings:
        reviews.append({
            'id': b.id,
            'client_name': b.client.fullname or b.client.username,
            'client_avatar': b.client.profile_pic.url if b.client.profile_pic else None,
            'rating': b.rating_given,
            'review': b.review_given or '',
            'date': b.completed_at.strftime('%d %b %Y') if b.completed_at else b.created_at.strftime('%d %b %Y'),
            'service_desc': b.service_desc
        })
        
    worker_data = {
        'id': worker.id,
        'fullname': worker.fullname,
        'email': worker.email,
        'phone': worker.phone,
        'skill': worker.skill or 'Artisan',
        'hourly_rate': worker.hourly_rate,
        'bio': worker.bio or "This expert hasn't written a biography yet.",
        'rating': float(worker.rating),
        'total_jobs': worker.total_jobs,
        'is_verified': worker.is_verified,
        'trust_score': worker.trust_score,
        'profile_pic': worker.profile_pic.url if worker.profile_pic else None,
        'date_joined': worker.date_joined.strftime('%d %b %Y') if worker.date_joined else 'N/A'
    }
    
    return Response({
        'status': 'success',
        'data': {
            'worker': worker_data,
            'reviews': reviews
        }
    }, status=200)


@csrf_exempt
@api_view(['POST']) # 🎯 Enforces matching the POST call from your HTML script
@authentication_classes([])
@permission_classes([AllowAny])
def flag_fraud(request, worker_id):
    try:
        # Pull the specific worker index pattern cleanly
        worker = User.objects.get(id=worker_id)
        worker.is_fraud = True      # Instantly locks their dashboard profile view
        worker.is_verified = False  # Suspends client search visibility flags
        worker.save()
        
        return Response({
            'status': 'success', 
            'message': f'Worker profile #{worker_id} successfully flagged as fraud.'
        }, status=200)
        
    except User.DoesNotExist:
        return Response({
            'status': 'error', 
            'message': 'Targeted artisan profile could not be found inside PostgreSQL records.'
        }, status=404)
    except Exception as e:
        return Response({
            'status': 'error', 
            'message': f'Internal engine breakdown: {str(e)}'
        }, status=500)
    
def get_authenticated_user_from_header(request):
    """
    Finds the exact user row matching the frontend session key.
    Completely eliminates cross-account data leaks.
    """
    # 1. If standard Django session cookies match, use them first
    if request.user and request.user.is_authenticated:
        return request.user
        
    # 2. Port Fallback: Search the database for the user who owns this custom token header
    token = request.headers.get('X-Session-Key')
    if token:
        try:
            return User.objects.get(session_key=token)
        except User.DoesNotExist:
            pass
            
    return None

User = get_user_model()


# 🎯 FORGOT PASSWORD API
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def forgot_password_api(request):
    """
    Safely resets a user's password from outside (Login page) 
    if their registered email exists in the system.
    """
    if request.method == 'POST':
        try:
            email = request.data.get('email')
            new_password = request.data.get('new_password')
            
            User_Model = get_user_model()
            
            try:
                user = User_Model.objects.get(email=email)
            except User_Model.DoesNotExist:
                return Response({'status': 'error', 'message': 'This email address is not registered!'}, status=400)
            
            user.set_password(new_password)
            user.save()
            
            return Response({'status': 'success', 'message': 'Password reset successfully!'})
            
        except Exception as e:
            return Response({'status': 'error', 'message': f'Server Error: {str(e)}'}, status=500)


from django.shortcuts import render

# --- FRONTEND PAGES VIEW ROUTING ---

def index_page(request):
    return render(request, 'index.html')

def login_page(request):
    return render(request, 'frontend_user/login.html')

def signup_page(request):
    return render(request, 'frontend_user/signup.html')

def forgot_password_page(request):
    return render(request, 'frontend_user/forgot_password.html')

def change_password_page(request):
    return render(request, 'frontend_user/change_password.html')

def dashboard_page(request):
    return render(request, 'frontend_user/dashboard.html')

def profile_page(request):
    return render(request, 'frontend_user/profile.html')

def services_page(request):
    return render(request, 'frontend_user/services.html')

def worker_list_page(request):
    return render(request, 'frontend_user/worker_list.html')

def worker_detail_page(request):
    return render(request, 'frontend_user/worker_detail.html')

def booking_request_page(request):
    return render(request, 'frontend_user/booking_request.html')

def booking_history_page(request):
    return render(request, 'frontend_user/booking_history.html')

def map_page(request):
    return render(request, 'frontend_user/map.html')

def user_messages_page(request):
    return render(request, 'frontend_user/user_messages.html')

def worker_signup_page(request):
    return render(request, 'frontend_worker/worker_signup.html')

def worker_dashboard_page(request):
    return render(request, 'frontend_worker/worker_dashboard.html')

def worker_profile_page(request):
    return render(request, 'frontend_worker/worker_profile.html')

def worker_booking_history_page(request):
    return render(request, 'frontend_worker/worker_booking_history.html')

def worker_requests_page(request):
    return render(request, 'frontend_worker/worker_requests.html')

def worker_messages_page(request):
    return render(request, 'frontend_worker/worker_messages.html')

def worker_search_page(request):
    return render(request, 'frontend_worker/worker_search.html')

def worker_detail_page_worker(request):
    return render(request, 'frontend_worker/worker_detail.html')

def worker_change_password_page(request):
    return render(request, 'frontend_worker/change_password.html')

def admin_dashboard_page(request):
    return render(request, 'frontend_admin/admin_dashboard.html')

def admin_users_page(request):
    return render(request, 'frontend_admin/admin_users.html')

def admin_verify_page(request):
    return render(request, 'frontend_admin/admin_verify.html')

def admin_booking_page(request):
    return render(request, 'frontend_admin/admin_booking.html')

def admin_fraud_page(request):
    return render(request, 'frontend_admin/admin_fraud.html')

def admin_settings_page(request):
    return render(request, 'frontend_admin/admin_settings.html')

def admin_analysis_page(request):
    return render(request, 'frontend_admin/admin_analysis.html')
        

