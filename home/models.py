from datetime import datetime
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django_countries.fields import CountryField
from django.utils.timesince import timesince
import pytz


TIMEZONE_CHOICES = [(tz, tz) for tz in pytz.all_timezones]

class Patient(models.Model):

    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    
    is_patient = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    firstname = models.CharField(max_length = 50, blank=True, null=True)
    surname = models.CharField(max_length = 50, blank=True, null=True)
    gender = models.BooleanField()
    dob = models.DateField()
    email = models.EmailField(max_length = 254)
    phone = models.CharField(max_length = 15)
    nationality = models.CharField(max_length = 40, blank=True, null=True)
    language = models.CharField(max_length = 20, blank=True, null=True)
    height = models.IntegerField(default=0)  
    height_unit = models.CharField(max_length=2, choices=[('cm', 'cm'), ('ft', 'ft')], default='cm')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    weight_unit = models.CharField(max_length=5, choices=[('kg', 'kg'), ('pound', 'pound')], default='kg')
    phone_country_code = models.CharField(max_length=10, blank=True, null=True)
    
    def __str__(self):
        if self.firstname:
            return self.firstname
        else:
            return f"Unnamed Patient ({self.user.email})"

class Language(models.Model):
    name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='language_photos/', default='language_photos/default.jpg')

    def __str__(self):
        return self.name

class Insurance(models.Model):
    name = models.CharField(max_length=255)
    website_link = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    photo = models.ImageField(upload_to='insurance_photos/', blank=True, null=True)

    def __str__(self):
        return self.name
    
class WorkingHours(models.Model):
    DAYS_OF_WEEK = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday'),
    ]

    hospital = models.ForeignKey('Hospital', on_delete=models.CASCADE, related_name='working_hours')
    day_of_week = models.CharField(max_length=9, choices=DAYS_OF_WEEK)
    open_time = models.TimeField()
    close_time = models.TimeField()

    def is_open_now(self, current_time):
        current_day = current_time.strftime('%A')
        current_time = current_time.time()
        return (self.day_of_week == current_day and
                self.open_time <= current_time <= self.close_time)

    def __str__(self):
        return f"{self.hospital.name} - {self.day_of_week}: {self.open_time} to {self.close_time}"

class Hospital(models.Model):
    def get_current_time():
        return timezone.now().time()
    
    name = models.CharField(max_length=255, null=True, blank=True)
    working_time = models.CharField(max_length=255, null=True, blank=True)
    supported_languages = models.ManyToManyField(Language)
    supported_insurance = models.ManyToManyField(Insurance, blank=True)
    address = models.TextField(null=True, blank=True)
    phone_number = models.CharField(max_length=50, null=True, blank=True)
    direct_billing = models.BooleanField(default=False)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    country = CountryField(blank_label='Select country', null=True, blank=True) 
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default='UTC') 
    link_map = models.CharField(max_length=255, null=True, blank=True)
    embed_map = models.TextField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    placeId = models.TextField(null=True, blank=True)
    last_api_update = models.DateTimeField(null=True, blank=True)
    user_ratings_total = models.IntegerField(null=True, blank=True)

    def is_open_now(self):
        now_utc = datetime.now(pytz.utc)
        hospital_tz = pytz.timezone(self.timezone)
        now_local = now_utc.astimezone(hospital_tz)
        current_day = now_local.strftime('%A')
        working_hours = self.working_hours.filter(day_of_week=current_day)
        for wh in working_hours:
            if wh.is_open_now(now_local):
                return True
        return False

    def __str__(self):
        return self.name

@receiver(pre_save, sender=Hospital)
def update_timezone(sender, instance, **kwargs):
    if instance.country:
        country_code = instance.country.code
        timezone = pytz.country_timezones.get(country_code)
        if timezone:
            instance.timezone = timezone[0]

class Review(models.Model):
    hospital = models.ForeignKey(Hospital, related_name='reviews', on_delete=models.CASCADE)
    author_name = models.CharField(max_length=255)
    author_url = models.URLField(max_length=500, null=True, blank=True)
    text = models.TextField()
    rating = models.DecimalField(max_digits=2, decimal_places=1)
    review_time = models.DateTimeField(default=timezone.now)
    profile_photo_url = models.URLField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f'Review by {self.author_name} for {self.hospital.name}'

    def time_since(self):
        time_since = timesince(self.review_time)
        first_unit = ' '.join(time_since.split()[:2])
        return first_unit.replace(',', '')


class TranslatedReview(models.Model):
    review = models.ForeignKey(Review, related_name='translations', on_delete=models.CASCADE)
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('ja', 'Japanese')])
    translated_text = models.TextField()

    def __str__(self):
        return f'Translation for {self.review.author_name} in {self.language}'

class HospitalImage(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='images')
    photo = models.ImageField(upload_to='hospital_photos/')
    original_url = models.URLField(max_length=1000, null=True, blank=True)
    unique_url = models.URLField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return f"{self.hospital.name}"

class Question(models.Model):
    text = models.TextField()
    is_first_question = models.BooleanField(default=False, help_text="Choose to ask this question as the first question.")

    def save(self, *args, **kwargs):
        if self.is_first_question:
            Question.objects.filter(is_first_question=True).update(is_first_question=False)
        super(Question, self).save(*args, **kwargs)

    def __str__(self):
        return self.text
    
class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text = models.TextField()
    likelihood_ratio = models.FloatField(null=True, blank=True, help_text="Likelihood ratio for this answer if applicable.")
    next_question = models.ForeignKey(Question, on_delete=models.SET_NULL, null=True, blank=True)
    is_conclusive = models.BooleanField(default=False)
    conclusion_text = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.text} (Question: {self.question.text})"
    
class Conclusion(models.Model):
    text = models.TextField()
    odds_condition = models.CharField(max_length=10, choices=[('>=1', 'Odds >= 1'), ('<1', 'Odds < 1')])
    answers = models.ManyToManyField(Answer, related_name='conclusions')
    
    def __str__(self):
        return self.text
    
class SymptomCheckSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symptom_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    conclusion_text = models.TextField()
    odds_percentage = models.TextField()
    id_conclusion = models.TextField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class FavouriteHospital(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favourite_hospitals')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='favourited_by')
    added_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'hospital')
        verbose_name_plural = 'Favourite Hospitals'

    def __str__(self):
        return f"{self.user.username} - {self.hospital.name}"
    
class DistanceInfo(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='distance_info')
    distance_text = models.CharField(max_length=100)
    duration_text = models.CharField(max_length=100)
    last_updated = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.distance_text}, {self.duration_text} to {self.hospital.name}"

class InsuranceInfo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='insurance_info')
    coverage = models.CharField(max_length=255)
    insurance_company = models.CharField(max_length=255, blank=True, null=True)
    policy_number = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.coverage}"
    
class HospitalBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symptom_checker')
    firstname = models.CharField(max_length=50, blank=True, null=True)
    surname = models.CharField(max_length=50, blank=True, null=True)
    gender = models.BooleanField()
    dob = models.DateField()
    email = models.EmailField(max_length=254)
    phone = models.CharField(max_length=30)
    phone_country_code = models.CharField(max_length=10, blank=True, null=True)

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    suggested_hospital = models.ForeignKey(Hospital, related_name='suggested_bookings', on_delete=models.CASCADE, null=True, blank=True)
    first_date = models.DateField(default=timezone.now)
    first_date_from = models.TimeField(default=timezone.now)
    first_date_to = models.TimeField(default=timezone.now)
    second_date = models.DateField(blank=True, null=True)
    second_date_from = models.TimeField(blank=True, null=True)
    second_date_to = models.TimeField(blank=True, null=True)
    first_date_reserved = models.DateField(blank=True, null=True)
    first_date_from_reserved = models.TimeField(blank=True, null=True)
    first_date_to_reserved = models.TimeField(blank=True, null=True)
    second_date_reserved = models.DateField(blank=True, null=True)
    second_date_from_reserved = models.TimeField(blank=True, null=True)
    second_date_to_reserved = models.TimeField(blank=True, null=True)
    more_info = models.TextField(blank=True, null=True)
    symptom = models.TextField(blank=True, null=True)
    duration = models.TextField(blank=True, null=True)

    coverage = models.CharField(max_length=255, blank=True)
    insuranceCompany = models.CharField(max_length=255, blank=True, null=True)
    policyNumber = models.CharField(max_length=255, blank=True, null=True)

    insurance_type = models.CharField(max_length=100, blank=True, null=True, choices=[
        ('cashless', 'Cashless Payment Supported'),
        ('insurance', 'Insurance supported (NOT CASHLESS)'),
        ('not_insurance', 'Insurance not supported')
    ])

    created_at = models.DateTimeField(auto_now_add=True)
    text_respond = models.TextField(blank=True, null=True) 
    text_reason = models.TextField(blank=True, null=True) 
    status = models.CharField(max_length=10,  default='waiting')
    utm_source = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.firstname} {self.surname} - {self.hospital.name if self.hospital else 'No Hospital'}"