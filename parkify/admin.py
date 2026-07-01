from django.contrib import admin
from .models import Signup, Booking,OwnerProfile, OwnerDocument, ParkingLot, PaymentTransaction
# Register your models here.

admin.site.register(Signup)
admin.site.register(Booking)
admin.site.register(OwnerProfile)
admin.site.register(OwnerDocument)
admin.site.register(ParkingLot)
admin.site.register(PaymentTransaction)