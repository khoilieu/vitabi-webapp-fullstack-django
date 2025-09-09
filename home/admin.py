from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Review, TranslatedReview, WorkingHours, HospitalBooking, InsuranceInfo, DistanceInfo, HospitalImage, Patient, Hospital, Language, Insurance, Question, Answer, Conclusion, SymptomCheckSession, FavouriteHospital
import pytz

# Register your models here.
class PatientAdmin(admin.ModelAdmin):
    list_display = ('email', 'firstname', 'surname', 'dob', 'gender', 'phone', 'is_verified')  # Thêm is_verified vào danh sách hiển thị
    search_fields = ('email', 'firstname', 'surname')

admin.site.register(Patient, PatientAdmin)  # Đăng ký Patient với PatientAdmin
admin.site.register(Language)
admin.site.register(Insurance)
admin.site.register(Question)
admin.site.register(Conclusion)
admin.site.register(SymptomCheckSession)
admin.site.register(FavouriteHospital)
admin.site.register(HospitalImage)
admin.site.register(DistanceInfo)
admin.site.register(InsuranceInfo)
admin.site.register(HospitalBooking)
admin.site.register(WorkingHours)
admin.site.register(Review)
admin.site.register(TranslatedReview)


class HospitalAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'timezone', 'link_map','embed_map')
    list_filter = ('country', 'timezone')
    search_fields = ('name', 'country')
    ordering = ('name',)

admin.site.register(Hospital, HospitalAdmin)

class AnswerAdmin(admin.ModelAdmin):
    list_display = ['text', 'question']

admin.site.register(Answer, AnswerAdmin)

class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    ordering = ('date_joined',) 

    def register_date(self, obj):
        return obj.date_joined

    register_date.short_description = 'Register Date'

admin.site.unregister(User)
admin.site.register(User, UserAdmin)