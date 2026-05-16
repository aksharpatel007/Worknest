from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
import uuid
from .models import User, Booking
from .serializers import UserSerializer, BookingSerializer

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

@csrf_exempt
@api_view(['POST'])
def login_view(request):
    """Authenticates user and redirects based on role."""
    email = request.data.get('email')
    password = request.data.get('password')
    user = authenticate(username=email, password=password)
    
    if user:
        key = str(uuid.uuid4()) 
        # Logic to send workers and clients to different dashboards
        redirect_page = 'worker_dashboard.html' if user.role_id == 2 else 'dashboard.html'
        return Response({
            'status': 'success',
            'session_key': key,
            'redirect': redirect_page
        })
    return Response({'status': 'error', 'message': 'Invalid login'}, status=401)

# --- PROFILE & WORKER LISTS ---

@api_view(['GET'])
def worker_list(request):
    """Returns only workers who have been verified by an admin."""
    workers = User.objects.filter(role_id=2, is_verified=True) 
    serializer = UserSerializer(workers, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@csrf_exempt
@api_view(['GET', 'POST'])
def profile_view(request):
    # This ensures the logged-in user only sees their own data
    user = request.user 
    if not user.is_authenticated:
         # Fallback for demo if frontend session isn't fully set
         user = User.objects.last()
    
    if request.method == 'GET':
        serializer = UserSerializer(user)
        return Response({'status': 'success', 'data': serializer.data})
    
    if request.method == 'POST':
        user.fullname = request.data.get('fullname', user.fullname)
        user.phone = request.data.get('phone', user.phone)
        if 'profile_pic' in request.FILES:
            user.profile_pic = request.FILES['profile_pic']
        user.save()
        return Response({'status': 'success', 'message': 'Profile updated!'})

# --- BOOKING & STATS LOGIC ---

@csrf_exempt
@api_view(['POST'])
def create_booking(request):
    """Handles new job requests from clients to verified workers."""
    try:
        worker_id = request.data.get('worker_id')
        client_id = request.data.get('client_id')
        service_desc = request.data.get('service_desc')

        client = User.objects.get(id=client_id)
        worker = User.objects.get(id=worker_id)

        # Security Check: Cannot book unverified workers
        if not worker.is_verified:
            return Response({'status': 'error', 'message': 'Worker is not verified yet.'}, status=400)

        booking = Booking.objects.create(
            client=client,
            worker=worker,
            service_desc=service_desc,
            status='pending'
        )
        return Response({'status': 'success', 'booking_id': booking.id})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)

@api_view(['GET'])
def user_bookings(request):
    """Fetches list of bookings for the logged-in user or worker."""
    user = request.user
    # Demo fallback
    if not user.is_authenticated:
        bookings = Booking.objects.all().order_by('-id')[:10]
    else:
        if user.role_id == 2:
            bookings = Booking.objects.filter(worker=user).order_by('-id')
        else:
            bookings = Booking.objects.filter(client=user).order_by('-id')
    
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

@api_view(['GET'])
def get_unverified_workers(request):
    """Queue for Admin to see who needs ID verification."""
    workers = User.objects.filter(role_id=2, is_verified=False)
    serializer = UserSerializer(workers, many=True)
    return Response({'status': 'success', 'data': serializer.data})

@api_view(['POST'])
def verify_worker(request, worker_id):
    try:
        worker = User.objects.get(id=worker_id)
        worker.is_verified = True
        worker.is_fraud = False # If we approve them, they aren't fraud
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
def get_all_bookings(request):
    """Fetches bookings, with optional filtering by client or worker."""
    try:
        bookings = Booking.objects.all().order_by('-created_at')
        
        # Filter by Client ID if provided in the URL
        client_id = request.query_params.get('client_id')
        if client_id:
            bookings = bookings.filter(client_id=client_id)
            
        # Filter by Worker ID if provided in the URL
        worker_id = request.query_params.get('worker_id')
        if worker_id:
            bookings = bookings.filter(worker_id=worker_id)
            
        serializer = BookingSerializer(bookings, many=True)
        return Response({'status': 'success', 'data': serializer.data})
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)
    

@api_view(['GET'])
def get_fraud_reports(request):
    # Filter for workers with a trust score below 50% or explicit reports
    low_trust_workers = User.objects.filter(role_id=2, trust_score__lt=50)
    serializer = UserSerializer(low_trust_workers, many=True)
    return Response({'status': 'success', 'data': serializer.data})


#
@api_view(['POST'])
def flag_fraud(request, worker_id):
    try:
        worker = User.objects.get(id=worker_id)
        worker.is_fraud = True      # This makes them appear in admin_fraud.html
        worker.is_verified = False  # This stops them from working
        worker.save()
        return Response({'status': 'success', 'message': 'Worker flagged as fraud'})
    except User.DoesNotExist:
        return Response({'status': 'error', 'message': 'Worker not found'}, status=404)