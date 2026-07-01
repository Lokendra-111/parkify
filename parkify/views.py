from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import models
from django.contrib.auth.hashers import make_password, check_password, identify_hasher
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from datetime import datetime, date
from math import ceil
import random
import string
from .models import Signup,Booking,OwnerProfile,OwnerDocument,ParkingLot,PaymentTransaction
from .tokens import signup_token_generator

# Landing Page
def home(request):
    return render(request, 'index.html')


# Authentication Page
def authentication(request):

    if request.method == "POST":

        action = request.POST.get('action')
# SIGNUP
    
        if action == "signup":

            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            username = request.POST.get('signup_username')
            email = request.POST.get('email')
            password = request.POST.get('signup_password')
            role = request.POST.get('signup_role', 'user')

            if Signup.objects.filter(username=username).exists():
                messages.error(request,"Username already exists. Please choose another username.")
                return redirect('authentication')

            if Signup.objects.filter(email=email).exists():
                messages.error(request,"Email already registered.")
                return redirect('authentication')

            Signup.objects.create(
                first_name=first_name,
                last_name=last_name,
                username=username,
                email=email,
                password=make_password(password),
                role=role
            )

            messages.success(
                request,
                "Account created successfully. Please login."
            )

            return redirect('authentication')

      
        # LOGIN
    
        elif action == "login":

            username = request.POST.get('login_username')
            password = request.POST.get('login_password')

            user = Signup.objects.filter(username=username).first()

            valid = False

            if user:
                try:
                    # Stored value is a recognised hash - verify normally.
                    identify_hasher(user.password)
                    valid = check_password(password, user.password)
                except ValueError:
                    # Legacy plaintext row (pre-migration). Verify directly,
                    # then upgrade it to a proper hash so it never happens again.
                    if user.password == password:
                        valid = True
                        user.password = make_password(password)
                        user.save(update_fields=['password'])

            if not user or not valid:
                messages.error(
                    request,
                    "Invalid username or password."
                )
                return redirect('authentication')

            # Store session
            request.session['user_id'] = user.id
            request.session['username'] = user.username
            request.session['role'] = user.role

            messages.success(
                request,
                f"Welcome {user.username}!"
            )

            # Redirect by role
            if user.role == 'admin':
                return redirect('admin_dashboard')

            elif user.role == 'owner':
                return redirect('owner_dashboard')

            else:
                return redirect('dashboard')

    return render(request, 'authentication.html')
# Admin Dashboard
def admin_dashboard(request):

    if not request.session.get('user_id'):
        return redirect('authentication')

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    admin = Signup.objects.get(id=request.session['user_id'])

    pending_owners = OwnerProfile.objects.filter(is_verified=False)

    owners = OwnerProfile.objects.all()

    parking_lots = ParkingLot.objects.all()

    bookings = Booking.objects.select_related('user').all().order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        bookings = bookings.filter(status=status_filter)

    total_revenue = PaymentTransaction.objects.filter(
        status='Success'
    ).aggregate(total=models.Sum('amount'))['total'] or 0

    active_bookings_count = Booking.objects.filter(status='Active').count()

    context = {
        'admin': admin,
        'pending_owners': pending_owners,
        'owners': owners,
        'parking_lots': parking_lots,
        'bookings': bookings,
        'status_filter': status_filter,
        'total_revenue': total_revenue,
        'active_bookings_count': active_bookings_count,
    }

    return render(request, 'admin_dashboard.html', context)

#Approve view
def approve_owner(request, owner_id):

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    owner = OwnerProfile.objects.get(id=owner_id)

    owner.is_verified = True
    owner.save()

    messages.success(
        request,
        "Owner approved successfully."
    )

    return redirect('admin_dashboard')

#Reject view
def reject_owner(request, owner_id):

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    owner = OwnerProfile.objects.get(id=owner_id)

    owner.is_verified = False
    owner.save()

    messages.error(
        request,
        "Owner rejected."
    )

    return redirect('admin_dashboard')

# User Dashboard
def dashboard(request):

    if not request.session.get('user_id'):
        return redirect('authentication')

    if request.session.get('role') != 'user':
        return redirect('authentication')

    user = Signup.objects.get(id=request.session['user_id'])

    return render(request, 'dashboard.html', {'user': user})


# Owner Dashboard
def owner_dashboard(request):

    if not request.session.get('user_id'):
        return redirect('authentication')

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner = Signup.objects.get(
        id=request.session['user_id']
    )

    parkings = []

    profile_exists = OwnerProfile.objects.filter(
        owner=owner
    ).exists()

    document_exists = False
    verification_status = "Not Started"

    if profile_exists:
        profile = OwnerProfile.objects.get(owner=owner)

        parkings = ParkingLot.objects.filter(
            owner=profile
        ).order_by('-created_at')

        document_exists = OwnerDocument.objects.filter(
            owner=profile
        ).exists()

        if document_exists:
            verification_status = (
                "Approved"
                if profile.is_verified
                else "Pending"
            )

    context = {
        'owner': owner,
        'parkings': parkings,
        'profile_exists': profile_exists,
        'document_exists': document_exists,
        'verification_status': verification_status,
    }

    return render(
        request,
        'owner_dashboard.html',
        context
    )
# Owner profile
def owner_profile(request):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(
        id=request.session['user_id']
    )

    if request.method == "POST":

        OwnerProfile.objects.update_or_create(
            owner=owner_user,

            defaults={
                'full_name': request.POST.get('full_name'),
                'company_name': request.POST.get('company_name'),
                'registration_no': request.POST.get('registration_no'),
                'phone': request.POST.get('phone'),
                'address': request.POST.get('address'),
            }
        )

        messages.success(request,"Profile saved successfully.")

        return redirect('owner_profile')

    return render(request,'owner_profile.html')

# Owner Document
def owner_document(request):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(id=request.session['user_id'])

    try:
        profile = OwnerProfile.objects.get(owner=owner_user)
    except OwnerProfile.DoesNotExist:
        messages.error(request,"Please complete your profile first.")
        return redirect('owner_profile')

    if request.method == "POST":

        document_mapping = {
        'citizenship': 'Citizenship',
        'pan_document': 'PAN Card',
        'business_registration': 'Business Registration',
        'parking_license': 'Parking License',
    }

    for field_name, document_type in document_mapping.items():

        uploaded_file = request.FILES.get(field_name)

        if uploaded_file:
            OwnerDocument.objects.create(
                owner=profile,
                document_id=f"{document_type}-{profile.id}",
                document_type=document_type,
                file_url=uploaded_file
            )

    messages.success(
        request,
        "Documents uploaded successfully."
    )

    return redirect('owner_dashboard')

    return render(request,'owner_document.html')
# Add Parking
def add_parking(request):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(
        id=request.session['user_id']
    )

    try:
        profile = OwnerProfile.objects.get(
            owner=owner_user
        )

    except OwnerProfile.DoesNotExist:

        messages.error(
            request,
            "Complete profile first."
        )

        return redirect('owner_profile')

    if not profile.is_verified:

        messages.error(
            request,
            "Admin verification required."
        )

        return redirect('owner_dashboard')

    if request.method == "POST":

        ParkingLot.objects.create(

            owner=profile,

            parking_name=request.POST.get(
                'parking_name'
            ),

            parking_image=request.FILES.get(
                'parking_image'
            ),

            location=request.POST.get(
                'location'
            ),

            latitude=request.POST.get(
                'latitude'
            ),

            longitude=request.POST.get(
                'longitude'
            ),

            car_capacity=request.POST.get(
                'car_capacity'
            ),

            bike_capacity=request.POST.get(
                'bike_capacity'
            ),

            rate_per_hour=request.POST.get(
                'rate_per_hour'
            ),

            map_link=request.POST.get(
                'map_link'
            ),

            description=request.POST.get(
                'description'
            )
        )

        messages.success(
            request,
            "Parking lot added successfully."
        )

        return redirect(
            'my_parking_lots'
        )

    return render(
        request,
        'add_parking.html'
    )
#my parking lot
def my_parking_lots(request):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(id=request.session['user_id'])

    profile = OwnerProfile.objects.get(owner=owner_user)
    parkings = ParkingLot.objects.filter(owner=profile).order_by('-created_at')

    return render(request,'my_parking_lots.html',{'parkings': parkings})

#edit
def edit_parking(request, parking_id):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(id=request.session['user_id'])
    profile = OwnerProfile.objects.get(owner=owner_user)

    parking = get_object_or_404(ParkingLot, id=parking_id, owner=profile)

    if request.method == "POST":

        parking.parking_name = request.POST.get('parking_name')
        parking.location = request.POST.get('location')
        parking.latitude = request.POST.get('latitude') or None
        parking.longitude = request.POST.get('longitude') or None
        parking.car_capacity = request.POST.get('car_capacity')
        parking.bike_capacity = request.POST.get('bike_capacity')
        parking.rate_per_hour = request.POST.get('rate_per_hour')
        parking.map_link = request.POST.get('map_link')
        parking.description = request.POST.get('description')
        parking.is_active = request.POST.get('is_active') == 'on'

        if request.FILES.get('parking_image'):
            parking.parking_image = request.FILES.get(
                'parking_image'
            )

        parking.save()

        messages.success(
            request,
            "Parking updated successfully."
        )

        return redirect('my_parking_lots')

    return render(
        request,
        'edit_parking.html',
        {
            'parking': parking
        }
    )

#delete
def delete_parking(request, parking_id):

    if request.session.get('role') != 'owner':
        return redirect('authentication')

    owner_user = Signup.objects.get(id=request.session['user_id'])
    profile = OwnerProfile.objects.get(owner=owner_user)

    parking = get_object_or_404(ParkingLot, id=parking_id, owner=profile)
    parking.delete()
    messages.success(request,"Parking deleted successfully.")
    return redirect('my_parking_lots')
#view
def view_parking(request, parking_id):

    parking = get_object_or_404(ParkingLot, id=parking_id, is_active=True)

    today = date.today().isoformat()

    car_booked = Booking.objects.filter(
        parking_name=parking.parking_name,
        vehicle_type='Car',
        booking_date=date.today(),
        status__in=['Pending', 'Active']
    ).count()

    bike_booked = Booking.objects.filter(
        parking_name=parking.parking_name,
        vehicle_type='Bike',
        booking_date=date.today(),
        status__in=['Pending', 'Active']
    ).count()

    context = {
        'parking': parking,
        'today': today,
        'car_available': max(parking.car_capacity - car_booked, 0),
        'bike_available': max(parking.bike_capacity - bike_booked, 0),
        'logged_in': bool(request.session.get('user_id')),
    }

    return render(request,'view_parking.html', context)


# Browse / Search Parking
def browse_parking(request):

    query = request.GET.get('q', '').strip()
    vehicle = request.GET.get('vehicle', '')
    sort = request.GET.get('sort', '')

    parkings = ParkingLot.objects.filter(is_active=True)

    if query:
        parkings = parkings.filter(location__icontains=query)

    if sort == 'price_low':
        parkings = parkings.order_by('rate_per_hour')
    elif sort == 'price_high':
        parkings = parkings.order_by('-rate_per_hour')
    else:
        parkings = parkings.order_by('-created_at')

    results = []
    today = date.today()

    for parking in parkings:

        car_booked = Booking.objects.filter(
            parking_name=parking.parking_name,
            vehicle_type='Car',
            booking_date=today,
            status__in=['Pending', 'Active']
        ).count()

        bike_booked = Booking.objects.filter(
            parking_name=parking.parking_name,
            vehicle_type='Bike',
            booking_date=today,
            status__in=['Pending', 'Active']
        ).count()

        car_available = max(parking.car_capacity - car_booked, 0)
        bike_available = max(parking.bike_capacity - bike_booked, 0)

        if vehicle == 'Car' and car_available <= 0:
            continue
        if vehicle == 'Bike' and bike_available <= 0:
            continue

        results.append({
            'parking': parking,
            'car_available': car_available,
            'bike_available': bike_available,
        })

    context = {
        'results': results,
        'query': query,
        'vehicle': vehicle,
        'sort': sort,
    }

    return render(request, 'browse_parking.html', context)


# Create a Booking
def book_parking(request, parking_id):

    if not request.session.get('user_id'):
        messages.error(request, "Please login to book a parking spot.")
        return redirect('authentication')

    if request.session.get('role') != 'user':
        messages.error(request, "Only users can book parking spots.")
        return redirect('authentication')

    parking = get_object_or_404(ParkingLot, id=parking_id, is_active=True)

    if request.method != "POST":
        return redirect('view_parking', parking_id=parking.id)

    user = Signup.objects.get(id=request.session['user_id'])

    vehicle_number = request.POST.get('vehicle_number', '').strip()
    vehicle_type = request.POST.get('vehicle_type')
    booking_date_str = request.POST.get('booking_date')
    check_in_str = request.POST.get('check_in')
    check_out_str = request.POST.get('check_out')

    if not all([vehicle_number, vehicle_type, booking_date_str, check_in_str, check_out_str]):
        messages.error(request, "Please fill in all booking details.")
        return redirect('view_parking', parking_id=parking.id)

    try:
        booking_date = datetime.strptime(booking_date_str, '%Y-%m-%d').date()
        check_in = datetime.strptime(check_in_str, '%H:%M').time()
        check_out = datetime.strptime(check_out_str, '%H:%M').time()
    except ValueError:
        messages.error(request, "Invalid date or time format.")
        return redirect('view_parking', parking_id=parking.id)

    if booking_date < date.today():
        messages.error(request, "Booking date cannot be in the past.")
        return redirect('view_parking', parking_id=parking.id)

    check_in_minutes = check_in.hour * 60 + check_in.minute
    check_out_minutes = check_out.hour * 60 + check_out.minute

    if check_out_minutes <= check_in_minutes:
        messages.error(request, "Check-out time must be after check-in time.")
        return redirect('view_parking', parking_id=parking.id)

    duration = ceil((check_out_minutes - check_in_minutes) / 60)

    capacity = parking.car_capacity if vehicle_type == 'Car' else parking.bike_capacity

    existing_bookings = Booking.objects.filter(
        parking_name=parking.parking_name,
        vehicle_type=vehicle_type,
        booking_date=booking_date,
        status__in=['Pending', 'Active']
    ).count()

    if existing_bookings >= capacity:
        messages.error(
            request,
            f"Sorry, no {vehicle_type} slots available at this parking lot for the selected date."
        )
        return redirect('view_parking', parking_id=parking.id)

    amount = duration * parking.rate_per_hour

    Booking.objects.create(
        user=user,
        parking_name=parking.parking_name,
        vehicle_number=vehicle_number,
        vehicle_type=vehicle_type,
        booking_date=booking_date,
        check_in=check_in,
        check_out=check_out,
        duration=duration,
        amount=amount,
        payment_status='Unpaid',
        status='Pending'
    )

    messages.success(
        request,
        f"Booking confirmed at {parking.parking_name}! Total amount: Rs {amount}"
    )

    booking = Booking.objects.filter(
        user=user, parking_name=parking.parking_name
    ).order_by('-created_at').first()

    return redirect('payment_page', booking_id=booking.id)


# Cancel a Booking
def cancel_booking(request, booking_id):

    if not request.session.get('user_id'):
        return redirect('authentication')

    booking = get_object_or_404(
        Booking, id=booking_id, user_id=request.session['user_id']
    )

    if booking.status in ['Pending', 'Active']:
        booking.status = 'Cancelled'
        booking.save()
        messages.success(request, "Booking cancelled successfully.")
    else:
        messages.error(request, "This booking can no longer be cancelled.")

    return redirect('my_bookings')


# ---- Payment Module ----
# Note: No live gateway keys are configured in this project yet, so this
# simulates a payment gateway redirect/callback (Card / eSewa / Khalti style)
# end-to-end. Swap process_payment's internals for the real SDK call when
# you have merchant credentials, the rest of the flow stays the same.

def _generate_txn_id():
    return 'TXN' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))


def payment_page(request, booking_id):

    if not request.session.get('user_id'):
        return redirect('authentication')

    booking = get_object_or_404(
        Booking, id=booking_id, user_id=request.session['user_id']
    )

    if booking.payment_status == 'Paid':
        messages.success(request, "This booking is already paid.")
        return redirect('my_bookings')

    if booking.status == 'Cancelled':
        messages.error(request, "Cannot pay for a cancelled booking.")
        return redirect('my_bookings')

    return render(request, 'payment.html', {'booking': booking})


def process_payment(request, booking_id):

    if not request.session.get('user_id'):
        return redirect('authentication')

    booking = get_object_or_404(
        Booking, id=booking_id, user_id=request.session['user_id']
    )

    if request.method != "POST":
        return redirect('payment_page', booking_id=booking.id)

    if booking.payment_status == 'Paid':
        messages.success(request, "This booking is already paid.")
        return redirect('my_bookings')

    method = request.POST.get('method')

    if method not in ('Card', 'Esewa', 'Khalti'):
        messages.error(request, "Please select a valid payment method.")
        return redirect('payment_page', booking_id=booking.id)

    # ---- Simulated gateway validation ----
    if method == 'Card':
        card_number = request.POST.get('card_number', '').replace(' ', '')
        expiry = request.POST.get('expiry', '')
        cvv = request.POST.get('cvv', '')

        if len(card_number) < 12 or not card_number.isdigit():
            messages.error(request, "Enter a valid card number.")
            return redirect('payment_page', booking_id=booking.id)

        if not expiry or not cvv or len(cvv) < 3:
            messages.error(request, "Enter valid card expiry and CVV.")
            return redirect('payment_page', booking_id=booking.id)

    else:
        wallet_id = request.POST.get('wallet_id', '').strip()

        if not wallet_id:
            messages.error(request, f"Enter your {method} registered mobile number.")
            return redirect('payment_page', booking_id=booking.id)

    # In a real integration this is where you'd redirect to the gateway and
    # later receive a server-to-server callback confirming success/failure.
    # Here we mark it Success immediately to complete the simulated flow.
    txn = PaymentTransaction.objects.create(
        booking=booking,
        txn_id=_generate_txn_id(),
        method=method,
        amount=booking.amount,
        status='Success'
    )

    booking.payment_status = 'Paid'
    if booking.status == 'Pending':
        booking.status = 'Active'
    booking.save()

    messages.success(request, "Payment successful!")

    return redirect('payment_receipt', txn_id=txn.txn_id)


def payment_receipt(request, txn_id):

    if not request.session.get('user_id'):
        return redirect('authentication')

    txn = get_object_or_404(
        PaymentTransaction, txn_id=txn_id, booking__user_id=request.session['user_id']
    )

    return render(request, 'payment_receipt.html', {'txn': txn, 'booking': txn.booking})


# ---- Admin: manage bookings & parking lots ----

def admin_update_booking(request, booking_id):

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    booking = get_object_or_404(Booking, id=booking_id)

    new_status = request.POST.get('status') if request.method == "POST" else request.GET.get('status')

    valid_statuses = dict(Booking.STATUS_CHOICES)

    if new_status not in valid_statuses:
        messages.error(request, "Invalid booking status.")
        return redirect('admin_dashboard')

    booking.status = new_status
    booking.save()

    messages.success(
        request,
        f"Booking #{booking.id} marked as {new_status}."
    )

    return redirect('admin_dashboard')


def admin_toggle_parking(request, parking_id):

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    parking = get_object_or_404(ParkingLot, id=parking_id)

    parking.is_active = not parking.is_active
    parking.save()

    messages.success(
        request,
        f"{parking.parking_name} is now {'Active' if parking.is_active else 'Inactive'}."
    )

    return redirect('admin_dashboard')


def admin_delete_parking(request, parking_id):

    if request.session.get('role') != 'admin':
        return redirect('authentication')

    parking = get_object_or_404(ParkingLot, id=parking_id)
    name = parking.parking_name
    parking.delete()

    messages.success(request, f"{name} has been removed by admin.")

    return redirect('admin_dashboard')
#my bookings
def my_bookings(request):

    if not request.session.get('user_id'):
        return redirect('authentication')

    bookings = Booking.objects.filter(user_id=request.session['user_id']).order_by('-created_at')

    return render(request,'my_bookings.html',{'bookings': bookings})
# Logout
def logout_view(request):
    request.session.flush()
    messages.success(request, "Logged out successfully.")
    return redirect('authentication')


# Forgot Password (custom flow for the Signup model)

def forgot_password(request):

    if request.method == "POST":

        email = request.POST.get('email', '').strip()
        user = Signup.objects.filter(email=email).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = signup_token_generator.make_token(user)

            reset_link = request.build_absolute_uri(
                f'/reset/{uid}/{token}/'
            )

            send_mail(
                subject="Reset your Parkify password",
                message=(
                    f"Hi {user.first_name},\n\n"
                    f"We received a request to reset your Parkify password. "
                    f"Click the link below to choose a new one:\n\n"
                    f"{reset_link}\n\n"
                    f"If you didn't request this, you can safely ignore this email."
                ),
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )

        # Always show the same message, whether or not the email exists,so this can't be used to check which emails are registered.
        messages.success(
            request,
            "If an account exists for that email, a reset link has been sent."
        )

        return redirect('password_reset_done')

    return render(request, 'forgot_password.html')


def password_reset_done(request):
    return render(request, 'password_reset_done.html')


def reset_password_confirm(request, uidb64, token):

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = Signup.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, Signup.DoesNotExist):
        user = None

    token_valid = user is not None and signup_token_generator.check_token(user, token)

    if not token_valid:
        messages.error(
            request,
            "This password reset link is invalid or has expired. Please request a new one."
        )
        return redirect('forgot_password')

    if request.method == "POST":

        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if len(new_password) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, 'reset_password.html', {'validlink': True})

        if new_password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'reset_password.html', {'validlink': True})

        user.password = make_password(new_password)
        user.save(update_fields=['password'])

        messages.success(request, "Your password has been reset successfully.")
        return redirect('password_reset_complete')

    return render(request, 'reset_password.html', {'validlink': True})


def password_reset_complete(request):
    return render(request, 'password_reset_complete.html')

# changing the password
@login_required
def change_password(request):

    if request.method == "POST":

        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")

        user = request.user

        # Check current password
        if not user.check_password(current_password):
            messages.error(request, "Current password is incorrect.")
            return redirect("dashboard")

        # Check password match
        if new_password != confirm_password:
            messages.error(request, "New passwords do not match.")
            return redirect("dashboard")

        # Prevent same password
        if current_password == new_password:
            messages.error(request, "New password cannot be the same as the current password.")
            return redirect("dashboard")

        # Change password
        user.set_password(new_password)
        user.save()

        # Keep user logged in
        update_session_auth_hash(request, user)

        messages.success(request, "Password changed successfully.")

        return redirect("dashboard")

    return redirect("dashboard")