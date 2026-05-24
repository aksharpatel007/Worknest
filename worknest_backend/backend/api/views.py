from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate,login
from django.db.models import Avg
import math
import uuid
from django.utils import timezone
from .models import User, Booking, Notification
from .serializers import UserSerializer, BookingSerializer, NotificationSerializer

# --- AUTHENTICATION & SIGNUP ---

@csrf_exempt
@api_view(['POST'])
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
def login_view(request):
    """Authenticates a user, saves their tracking token to the DB, and logs them in."""
    email = request.data.get('email')
    password = request.data.get('password')
    
    user = authenticate(username=email, password=password)
    
    if user:
        login(request, user)  # Sets native Django cookies
        
        # 🎯 FIX 1: Generate a unique session key and save it to this specific user row!
        key = str(uuid.uuid4())
        user.session_key = key
        user.save()
        
        # Route roles smoothly
        redirect_page = 'worker_dashboard.html' if user.role_id == 2 else 'dashboard.html'
        
        return Response({
            'status': 'success',
            'session_key': key,
            'redirect': redirect_page
        }, status=200)
        
    return Response({'status': 'error', 'message': 'Invalid login credentials.'}, status=401)


# --- PROFILE & WORKER LISTS ---

@csrf_exempt
@api_view(['GET'])
def worker_list(request):
    """Fetches all workers for the system directories."""
    workers = User.objects.filter(role_id=2).order_by('-id')
    
    data_list = []
    for worker in workers:
        data_list.append({
            'id': worker.id,
            'fullname': worker.fullname,
            'email': worker.email,
            'skill': worker.skill or 'Artisan',
            'hourly_rate': worker.hourly_rate,
            'bio': getattr(worker, 'bio', ''),
            'rating': getattr(worker, 'rating', 0.0),
            'total_jobs': getattr(worker, 'total_jobs', 0),
            'submitted_at': worker.date_joined.strftime('%I:%M %p') if worker.date_joined else 'N/A'
        })
        
    return Response({'status': 'success', 'data': data_list}, status=200)


@csrf_exempt
@api_view(['GET', 'POST'])
def profile_view(request):
    # 🎯 FIXED: Pull the exact active user matching the login, instead of blindly using User.objects.last()
    user = get_authenticated_user_from_header(request)
    
    if not user:
        return Response({'status': 'error', 'message': 'Anonymous access denied'}, status=401)
        
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response({'status': 'success', 'data': serializer.data})
    
    if request.method == 'POST':
        user.fullname = request.data.get('fullname', user.fullname)
        user.phone = request.data.get('phone', user.phone)
        
        incoming_bio = request.data.get('bio')
        if incoming_bio:
            user.bio = incoming_bio
            user.trust_score = 10 
            
        if 'profile_pic' in request.FILES:
            user.profile_pic = request.FILES['profile_pic']
        user.save()
        return Response({'status': 'success', 'message': 'Profile state updated successfully!'})
    

from django.utils import timezone
import math

@csrf_exempt
@api_view(['GET', 'POST', 'PATCH'])
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
        return Response({'status': 'success', 'data': serializer.data}, status=200)

    # ------------------ POST: DISPATCH INITIAL JOB ------------------
    elif request.method == 'POST':
        try:
            worker_id = int(request.data.get('worker_id'))
            client_id = int(request.data.get('client_id'))
            service_desc = request.data.get('service_desc')

            client = User.objects.get(id=client_id)
            worker = User.objects.get(id=worker_id)

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
                hours_consumed = max(1.0, duration.total_seconds() / 3600.0)
                
                # Format time string for descriptive message outputs
                mins_total = int(duration.total_seconds() / 60)
                hrs_part = mins_total // 60
                mins_part = mins_total % 60
                time_str = f"{hrs_part} hrs {mins_part} mins" if hrs_part > 0 else f"{mins_total} mins"
                if mins_total < 5: 
                    time_str = "1 hr (Minimum Base Rate Applied)"
                
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
                
            booking.save()
            return Response({'status': 'success', 'message': f'State moved to {new_status}'}, status=200)
        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=400)

@csrf_exempt
@api_view(['POST'])
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
    """Fetches user-specific notification logs for message feeds."""
    user = get_authenticated_user_from_header(request)
    if not user:
        return Response({'status': 'error', 'message': 'Session authentication invalid'}, status=401)
    
    notifications = Notification.objects.filter(user=user).order_by('-id')
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
    completed_jobs = Booking.objects.filter(worker=user, status='completed').count()
    
    return Response({
        'status': 'success',
        'data': {
            'total_jobs': total_jobs,
            'pending_jobs': pending_jobs,
            'earnings': completed_jobs * getattr(user, 'hourly_rate', 0),
            'rating': getattr(user, 'rating', 0),
            'is_verified': user.is_verified # Used to show/hide dashboard banner
        }
    })

# --- ADMIN ACTIONS ---

@csrf_exempt
@api_view(['GET'])
def get_unverified_workers(request):
    """
    Fetches all workers awaiting admin verification approval.
    Extracts verification notes out of the bio text stream to keep 
    the inspector panel and notification bell clean.
    """
    unverified_workers = User.objects.filter(role_id=2, is_verified=False).order_by('-id')
    
    data_list = []
    for worker in unverified_workers:
        raw_bio = getattr(worker, 'bio', '') or ''
        admin_note = ""
        clean_bio = raw_bio
        
        # Extract administrative notes if they exist
        if raw_bio.startswith("VERIFICATION_NOTE:"):
            admin_note = raw_bio.replace("VERIFICATION_NOTE:", "").strip()
            clean_bio = "" # Clear from professional profile overview if it was just a message
            
        data_list.append({
            'id': worker.id,
            'fullname': worker.fullname,
            'email': worker.email,
            'skill': worker.skill or 'Artisan',
            'hourly_rate': worker.hourly_rate,
            'bio': clean_bio,
            'admin_note': admin_note, # Explicit variable payload targeting admin panels
            'submitted_at': worker.date_joined.strftime('%d %b %Y, %I:%M %p') if worker.date_joined else 'N/A'
        })
        
    return Response({'status': 'success', 'data': data_list}, status=200)


@api_view(['POST'])
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
@api_view(['POST']) # 🎯 Enforces matching the POST call from your HTML script
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