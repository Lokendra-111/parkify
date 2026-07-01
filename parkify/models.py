from django.db import models
class Signup(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('owner', 'Owner'),
        ('admin', 'Admin'),
    )

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.username} ({self.role})"
    

#owner profile 
class OwnerProfile(models.Model):

    owner = models.OneToOneField(Signup,on_delete=models.CASCADE)

    full_name = models.CharField(max_length=150)

    company_name = models.CharField(max_length=150)

    registration_no = models.CharField(max_length=100)

    phone = models.CharField(max_length=20)

    address = models.TextField()

    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.full_name
  #owner document    
class OwnerDocument(models.Model):

    owner = models.ForeignKey(OwnerProfile,on_delete=models.CASCADE)

    document_id = models.CharField(max_length=100)
    
    document_type = models.CharField(max_length=100)

    file_url = models.FileField(upload_to='documents/')

    upload_date = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20,default='Pending')

    def __str__(self):
        return self.document_type 


# Parking Lot
class ParkingLot(models.Model):
    owner = models.ForeignKey(OwnerProfile,on_delete=models.CASCADE)

    parking_name = models.CharField(max_length=150)

    parking_image = models.ImageField(upload_to='parking_images/',blank=True,null=True)

    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    longitude = models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)

    car_capacity = models.IntegerField()

    bike_capacity = models.IntegerField()

    rate_per_hour = models.DecimalField(max_digits=10,decimal_places=2)

    map_link = models.URLField(blank=True, null=True)

    description = models.TextField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)



 #Bookings module   
class Booking(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Active', 'Active'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled')
    ]

    PAYMENT_CHOICES = [
        ('Paid', 'Paid'),
        ('Unpaid', 'Unpaid')
    ]

    user = models.ForeignKey(Signup,on_delete=models.CASCADE)

    parking_name = models.CharField(max_length=150)

    vehicle_number = models.CharField(max_length=30)

    vehicle_type = models.CharField(max_length=20)

    booking_date = models.DateField()

    check_in = models.TimeField()

    check_out = models.TimeField()

    duration = models.IntegerField()

    amount = models.DecimalField(max_digits=10,decimal_places=2)

    payment_status = models.CharField(max_length=20,choices=PAYMENT_CHOICES)

    status = models.CharField(max_length=20,choices=STATUS_CHOICES,default='Pending')

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Booking #{self.id}"


# Payment module
class PaymentTransaction(models.Model):

    METHOD_CHOICES = [
        ('Card', 'Credit/Debit Card'),
        ('Esewa', 'eSewa'),
        ('Khalti', 'Khalti'),
    ]

    STATUS_CHOICES = [
        ('Success', 'Success'),
        ('Failed', 'Failed'),
    ]

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='transactions')

    txn_id = models.CharField(max_length=40, unique=True)

    method = models.CharField(max_length=20, choices=METHOD_CHOICES)

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Success')

    paid_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.txn_id} - {self.status}"