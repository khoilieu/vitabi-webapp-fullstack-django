from django import forms
from .models import WorkingHours, Hospital, HospitalImage, DistanceInfo

class WorkingHoursForm(forms.ModelForm):
    class Meta:
        model = WorkingHours
        fields = '__all__'

class HospitalForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = '__all__'

class HospitalImageForm(forms.ModelForm):
    class Meta:
        model = HospitalImage
        fields = '__all__'

class DistanceInfoForm(forms.ModelForm):
    class Meta:
        model = DistanceInfo
        fields = '__all__'
