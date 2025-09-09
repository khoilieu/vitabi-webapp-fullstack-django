from collections import defaultdict
from itertools import chain
from operator import attrgetter
from urllib.parse import urlencode
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from googletrans import Translator
from unidecode import unidecode
import pytz

from home.forms import DistanceInfoForm, HospitalForm, HospitalImageForm, WorkingHoursForm
from vitabi.settings import TIMEZONE_DISPLAY
from .models import DistanceInfo, HospitalBooking, HospitalImage, Insurance, InsuranceInfo, Patient, Hospital, Question, Answer, Conclusion, Review, SymptomCheckSession, FavouriteHospital, TranslatedReview, WorkingHours
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.utils import translation, timezone
from django.utils.translation import get_language_info, get_language, gettext as _
from datetime import datetime, time
from django.db.models import Case, When, Value, BooleanField, IntegerField
from django.db.models import Count
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
import requests
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
import json
from django.core.mail import send_mail
import random
import string
from django.db.models import Q
from django.utils.dateparse import parse_date

def distance_info_list(request):
    distances = DistanceInfo.objects.all()
    return render(request, 'admin/distance_info_list.html', {'distances': distances})

def distance_info_create(request):
    form = DistanceInfoForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('distance_info_list')
    return render(request, 'admin/distance_info_form.html', {'form': form})

def distance_info_update(request, id):
    distance = get_object_or_404(DistanceInfo, id=id)
    form = DistanceInfoForm(request.POST or None, instance=distance)
    if form.is_valid():
        form.save()
        return redirect('distance_info_list')
    return render(request, 'admin/distance_info_form.html', {'form': form})

def distance_info_delete(request, id):
    distance = get_object_or_404(DistanceInfo, id=id)
    if request.method == 'POST':
        distance.delete()
        return redirect('distance_info_list')
    return render(request, 'admin/distance_info_confirm_delete.html', {'object': distance})

def hospital_image_list(request):
    images = HospitalImage.objects.all()
    return render(request, 'admin/hospital_image_list.html', {'images': images})

def hospital_image_create(request):
    form = HospitalImageForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        form.save()
        return redirect('hospital_image_list')
    return render(request, 'admin/hospital_image_form.html', {'form': form})

def hospital_image_update(request, id):
    image = get_object_or_404(HospitalImage, id=id)
    form = HospitalImageForm(request.POST or None, request.FILES or None, instance=image)
    if form.is_valid():
        form.save()
        return redirect('hospital_image_list')
    return render(request, 'admin/hospital_image_form.html', {'form': form})

def hospital_image_delete(request, id):
    image = get_object_or_404(HospitalImage, id=id)
    if request.method == 'POST':
        image.delete()
        return redirect('hospital_image_list')
    return render(request, 'admin/hospital_image_confirm_delete.html', {'object': image})

def hospital_list(request):
    hospitals = Hospital.objects.all()
    return render(request, 'admin/hospital_list.html', {'hospitals': hospitals})

def hospital_create(request):
    form = HospitalForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('hospital_list')
    return render(request, 'admin/hospital_form.html', {'form': form})

def hospital_update(request, id):
    hospital = get_object_or_404(Hospital, id=id)
    form = HospitalForm(request.POST or None, instance=hospital)
    if form.is_valid():
        form.save()
        return redirect('hospital_list')
    return render(request, 'admin/hospital_form.html', {'form': form})

def hospital_delete(request, id):
    hospital = get_object_or_404(Hospital, id=id)
    if request.method == 'POST':
        hospital.delete()
        return redirect('hospital_list')
    return render(request, 'admin/hospital_confirm_delete.html', {'object': hospital})

def working_hours_list(request):
    hours = WorkingHours.objects.all()
    return render(request, 'admin/working_hours_list.html', {'hours': hours})

def working_hours_create(request):
    form = WorkingHoursForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('working_hours_list')
    return render(request, 'admin/working_hours_form.html', {'form': form})

def working_hours_update(request, id):
    hour = get_object_or_404(WorkingHours, id=id)
    form = WorkingHoursForm(request.POST or None, instance=hour)
    if form.is_valid():
        form.save()
        return redirect('working_hours_list')
    return render(request, 'admin/working_hours_form.html', {'form': form})

def working_hours_delete(request, id):
    hour = get_object_or_404(WorkingHours, id=id)
    if request.method == 'POST':
        hour.delete()
        return redirect('working_hours_list')
    return render(request, 'admin/working_hours_confirm_delete.html', {'object': hour})

@csrf_exempt
def list_booked_hospital(request):
    is_patient = request.user.patient.is_patient
    if is_patient:
        return redirect('home')
    
    hospitalbooking = HospitalBooking.objects.prefetch_related('hospital__working_hours').order_by(
        Case(
            When(status='waiting', then=Value(1)), 
            default=Value(2),
            output_field=IntegerField(),
        ),
        'created_at' 
    )
    
    hospitals = Hospital.objects.all() 
    for booking in hospitalbooking:
        booking.formatted_working_hours = [
            {
                'day': _(wh.day_of_week),
                'time': f"{wh.open_time.strftime('%H:%M')} - {wh.close_time.strftime('%H:%M')}"
            }
            for wh in booking.hospital.working_hours.all()
        ]
        booking.timezone_str = TIMEZONE_DISPLAY.get(booking.hospital.timezone, 'UTC')

        if 'Sunday' not in [hours.day_of_week for hours in booking.hospital.working_hours.all()]:
            booking.formatted_working_hours.append({'day': _('Sunday'), 'time': 'Closed'})


    total_bookings = hospitalbooking.count()
    waiting_count = hospitalbooking.filter(status='waiting').count()
    cancel_count = hospitalbooking.filter(status='canceled').count()
    approved_count = hospitalbooking.filter(status='approved').count()
    rejected_count = hospitalbooking.filter(status='rejected').count()
    closed_count = hospitalbooking.filter(status__in=['approved', 'rejected','canceled']).count()

    stats = {
        'total_bookings': total_bookings,
        'waiting_count': waiting_count,
        'cancel_count': cancel_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'closed_count': closed_count
    }

    return render(request, 'admin/adminBookedHospital.html', {'hospitalbooking': hospitalbooking, 'stats': stats, 'hospitals': hospitals})

@csrf_exempt
def approve_booked_hospital(request, booked_id):
    bookedHospital = get_object_or_404(HospitalBooking, id=booked_id)
    approve = request.GET.get('approve')

    if request.method == "POST" and approve == "app":
        selected_hospital_id = int(request.POST.get('approve_hospital'))
        selected_hospital = Hospital.objects.get(id=selected_hospital_id)
        appointment_date = request.POST.get('appointment_date')
        formatted_date = parse_date(appointment_date).strftime('%m/%d')
        appointment_time_from = request.POST.get('appointment_time_from')
        appointment_time_to = request.POST.get('appointment_time_to')
        insurance_option = request.POST.get('insurance_option')
        
        if selected_hospital != bookedHospital.hospital: # The hospital is changed
            #do something
            bookedHospital.suggested_hospital = selected_hospital
            full_respond = f"{_('Suggested hospital is')} {selected_hospital.name}. {_('Appointment Date')}: {formatted_date}, {_('Time From')}: {appointment_time_from} {_('to')} {appointment_time_to}"    
        else: # not change hospital
            bookedHospital.suggested_hospital = None
            full_respond = f"{_('You have an appointment at')} {selected_hospital.name}. {_('Appointment Date')}: {formatted_date}, {_('Time From')}: {appointment_time_from} {_('to')} {appointment_time_to}"


        bookedHospital.status = 'approved'
        if full_respond:
            bookedHospital.text_respond = full_respond
        bookedHospital.first_date_reserved = appointment_date
        bookedHospital.first_date_from_reserved = appointment_time_from
        bookedHospital.first_date_to_reserved = appointment_time_to
        bookedHospital.insurance_type = insurance_option
        bookedHospital.save()

        hospital_url = request.build_absolute_uri(reverse('hospitalInfo', kwargs={'pk': bookedHospital.hospital.id}))
        google_maps_url = f"{bookedHospital.hospital.link_map}"

        new_hospital_url = request.build_absolute_uri(reverse('hospitalInfo', kwargs={'pk': selected_hospital_id}))
        new_google_maps_url = f"{selected_hospital.link_map}"

        timezone_str = TIMEZONE_DISPLAY.get(bookedHospital.hospital.timezone, 'UTC')

        visiting_time_display = f"{appointment_time_from}~{appointment_time_to} on {formatted_date} ({timezone_str})"

        hello_str = _("Hello Mr.") if bookedHospital.gender else _("Hello Ms.")

        home_url = request.build_absolute_uri(reverse('home'))

        current_language = get_language()

        if current_language == 'jp':
            insuranceSupport = ""
            if insurance_option == "cashless":
                insuranceSupport += f"こちらの病院では保険会社のキャッシュレス決済をご利用可能いただけます。病院へ行く際には、以下の3点をご用意ください。<br>1. パスポートまたは写真付き身分証明書<br>2. 保険証および保険証番号<br>3. 保険請求書 (お持ちの場合)<br><br>ご意見やご不明点がある場合は、どうぞお気軽に本メールへご返信くださいませ。<br><br>{bookedHospital.surname}様の早いご回復をお祈りしております。"
            elif insurance_option == "insurance":
                insuranceSupport += f"こちらの病院では保険会社のキャッシュレス決済がご利用いただけません。一度、{bookedHospital.surname}様が立て替えていただき、のちに保険会社へ請求をする形になります。<br><br>保険会社の請求には診断書が必要になる為、必ず医師から受け取るようにしてください。<br><br><a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a><br><br>この度はご迷惑をおかけし、誠に申し訳ございませんでした。<br><br>ご理解のほどよろしくお願い申し上げます。"      
            elif insurance_option == "not_insurance":
                insuranceSupport += f"{bookedHospital.surname}様の予約は以下の理由から、保険対象外になります。<br><br><a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a><br><br>この度はご迷惑をおかけし、誠に申し訳ございませんでした。<br><br>ご理解のほどよろしくお願い申し上げます。"
            approved_email_content = f"""
<html>
<body>
    <p>{bookedHospital.firstname} {bookedHospital.surname} 様</p>
    <p>株式会社Vitabiでございます。</p>
    <p>{bookedHospital.hospital.name} への予約リクエストが承認されましたので、ご連絡いたしました。</p>
    <p>以下はご予約の詳細です。</p>
    
    <ul>
        <li>病院名: <a href='{hospital_url}'>{bookedHospital.hospital.name}</a></li>
        <li>住所: <a href='{google_maps_url}'>{bookedHospital.hospital.address}</a></li>
        <li>ご予約の時間: {visiting_time_display}</li>
        <li>保険: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>保険証番号: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>症状: {bookedHospital.symptom}</li>
        <li>期間: {bookedHospital.duration}</li>
    </ul>

    {insuranceSupport}

    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""
            approved_email_content_new_hospital = f"""
<html>
<body>
    <p>{bookedHospital.firstname} {bookedHospital.surname} 様</p>
    <p>お世話になっております。</p>
    <p>株式会社Vitabiでございます。</p>
    <p>ただいま病院の予約が完了しましたので、ご連絡いたしました。</p>
    <p>ただし、{bookedHospital.surname}様のご希望いただきました病院は予約で一杯だったため、保険会社により病院を変更させていただきました。</p>
    <p>以下はご予約の詳細です。</p>
    
    <ul>
        <li>病院名: <a href='{new_hospital_url}'>{selected_hospital.name}</a></li>
        <li>住所: <a href='{new_google_maps_url}'>{selected_hospital.address}</a></li>
        <li>ご予約の時間: {visiting_time_display}</li>
        <li>保険: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>保険証番号: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>症状: {bookedHospital.symptom}</li>
        <li>期間: {bookedHospital.duration}</li>
    </ul>

    {insuranceSupport}

    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""
        else:
            insuranceSupport = ""
            if insurance_option == "cashless":
                insuranceSupport += f"As this hospital supports Cashless Medical Service, please don't forget to bring the following items when visiting: <br> 1. Your passport or photo ID <br> 2. Your insurance document with policy number <br> 3. Insurance claim form (if you have one)"
            elif insurance_option == "insurance" :
                insuranceSupport += f"We regret to inform you that our hospital does not currently support cashless medical services. Therefore, you will need to make out-of-pocket payments for any medical services received with medical certificate. Subsequently, you can file a claim with your insurance company for reimbursement.<br><br>We apologize for any inconvenience this may cause and appreciate your understanding. If you have any questions or require further assistance, please do not hesitate to contact us. Thank you for your cooperation."
            elif insurance_option == "not_insurance":
                insuranceSupport += f"We regret to inform you that your insurance company does not support the coverage for your upcoming appointment [No Insurance Reason]. As a result, you will need to pay out of pocket for this service.<br><br>We apologize for any inconvenience this may cause and appreciate your understanding. If you have any questions or need further assistance, please do not hesitate to contact us. Thank you for your cooperation."
            approved_email_content = f"""
<html>
<body>
    <p>{hello_str} {bookedHospital.surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("I am pleased to inform you that your booking request to")} <a href='{hospital_url}'>{bookedHospital.hospital.name}</a> {_("has been approved")}.</p>

    <p>{_("Here are the details of your visit")}:</p>

    <ul>
        <li>{_("Approved Hospital")}: <a href='{hospital_url}'>{bookedHospital.hospital.name}</a></li>
        <li>{_("Address")}: <a href='{google_maps_url}'>{bookedHospital.hospital.address}</a></li>
        <li>{_("Visiting Time")}: {visiting_time_display}</li>
        <li>{_("Insurance")}: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>{_("Policy Number")}: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>{_("Symptom")}: {bookedHospital.symptom}</li>
        <li>{_("Duration")}: {bookedHospital.duration}</li>
    </ul>

    {insuranceSupport}

    <p>{_("We wish you a speedy recovery.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_("Nhat Lieu")}<br>{_("CEO of Vitabi")}</p>
</body>
</html>
"""
            approved_email_content_new_hospital = f"""
<html>
<body>
    <p>{hello_str} {bookedHospital.surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("I am pleased to inform you that your appointment has been confirmed. However, due to the hospital's availability, the hospital for your visit has been changed.")}</p>

    <p>{_("Here are the details of your visit")}:</p>

    <ul>
        <li>{_("New Hospital")}: <a href='{new_hospital_url}'>{selected_hospital.name}</a></li>
        <li>{_("Address")}: <a href='{new_google_maps_url}'>{selected_hospital.address}</a></li>
        <li>{_("Visiting Time")}: {visiting_time_display}</li>
        <li>{_("Insurance")}: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>{_("Policy Number")}: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>{_("Symptom")}: {bookedHospital.symptom}</li>
        <li>{_("Duration")}: {bookedHospital.duration}</li>
    </ul>

    {insuranceSupport}

    <p>{_("We wish you a speedy recovery.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_("Nhat Lieu")}<br>{_("CEO of Vitabi")}</p>
</body>
</html>
"""
        send_mail(
            _('Your Appointment Has Been Confirmed with a New Hospital') if selected_hospital != bookedHospital.hospital else _('Your Appointment Request Has Been Approved'),
            _('Please see the message in HTML format.'),
            'Vitabi <vitabi.info@gmail.com>',
            [bookedHospital.email],
            fail_silently=False,
            html_message=approved_email_content_new_hospital if selected_hospital != bookedHospital.hospital else approved_email_content
        )

    elif request.method == "GET" and approve == "dis":
        bookedHospital.status = 'waiting'
        bookedHospital.save()
    
    return redirect('list_booked_hospital')

@csrf_exempt
def reject_booked_hospital(request, booked_id):
    if request.method == "POST":
        bookedHospital = get_object_or_404(HospitalBooking, id=booked_id)
        reject_reason = request.POST.get("reject_reason")

        bookedHospital.text_reason = reject_reason
        bookedHospital.text_respond = ""
        bookedHospital.status = 'rejected'
        bookedHospital.save()
        current_language = get_language()
        home_url = request.build_absolute_uri(reverse('home'))
        hello_str = _("Hello Mr.") if bookedHospital.gender else _("Hello Ms.")

        if current_language == 'jp':
            rejected_email_content = f"""
<html>
<body>
    <p>{bookedHospital.firstname} {bookedHospital.surname} 様</p>

    <p>お世話になっております。</p>

    <p>株式会社Vitabiでございます。</p>

    <p>残念ながら、[{reject_reason}] によりご予約をキャンセルさせていただきました。ご不便をおかけしますことを心よりお詫び申し上げます。</p>

    <a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a>

    <p>この度はご迷惑をおかけし、誠に申し訳ございませんでした。</p>

    <p>ご理解のほどよろしくお願い申し上げます。</p>

    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""
        else:
            rejected_email_content = f"""
<html>
<body>
    <p>{hello_str} {bookedHospital.surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("I regret to inform you that your appointment has been canceled")}.</p>

    <p>{_("Cancel Reason")}: {reject_reason}</p>

    <p>{_("We sincerely apologize for any inconvenience this may cause.")}</p>

    <a href='{home_url}'>If you have any questions or need assistance with rescheduling, please do not hesitate to contact our support team by replying to this email or booking with Vitabi</a>

    <p>{_("We are truly sorry for this situation and appreciate your understanding.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_("Nhat Lieu")}<br>{_("CEO of Vitabi")}</p>
</body>
</html>
"""

        send_mail(
            _('Your Appointment Has Been Rejected'),
            _('Please see the message in HTML format.'),
            'Vitabi <vitabi.info@gmail.com>',  
            [bookedHospital.email],  
            fail_silently=False,
            html_message=rejected_email_content
        )

    return redirect('list_booked_hospital')
@csrf_exempt
def cancel_booked_hospital(request, booked_id):
    if request.method == "POST":
        bookedHospital = get_object_or_404(HospitalBooking, id=booked_id)
        cancel_reason = request.POST.get("cancel_reason")

        bookedHospital.text_reason = cancel_reason
        bookedHospital.text_respond = ""

        bookedHospital.status = 'canceled'
        bookedHospital.save()

        current_language = get_language()
        home_url = request.build_absolute_uri(reverse('home'))
        hello_str = _("Hello Mr.") if bookedHospital.gender else _("Hello Ms.")

        if current_language == 'jp':
            canceled_email_content = f"""
<html>
<body>
    <p>{bookedHospital.firstname} {bookedHospital.surname} 様</p>

    <p>お世話になっております。</p>

    <p>株式会社Vitabiでございます。</p>

    <p>残念ながら、下記の理由によりご予約を受け付けることが出来ませんでした。ご不便をおかけしますことを心よりお詫び申し上げます。</p>

    <p>キャンセル理由：{cancel_reason}</p>

    <a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a>

    <p>この度はご迷惑をおかけし、誠に申し訳ございませんでした。</p>

    <p>ご理解のほどよろしくお願い申し上げます。</p>

    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""
        else:
            canceled_email_content = f"""
<html>
<body>
    <p>{hello_str} {bookedHospital.surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("I regret to inform you that your appointment has been canceled")}.</p>

    <p>{_("Cancel Reason")}: {cancel_reason}</p>

    <p>{_("We sincerely apologize for any inconvenience this may cause.")}</p>

    <a href='{home_url}'>If you have any questions or need assistance with rescheduling, please do not hesitate to contact our support team by replying to this email or booking with Vitabi</a>

    <p>{_("We are truly sorry for this situation and appreciate your understanding.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_("Nhat Lieu")}<br>{_("CEO of Vitabi")}</p>
</body>
</html>
"""

        send_mail(
            _('Your Appointment Has Been Canceled'),
            _('Please see the message in HTML format.'),
            'Vitabi <vitabi.info@gmail.com>',  
            [bookedHospital.email],  
            fail_silently=False,
            html_message=canceled_email_content
        )

    return redirect('list_booked_hospital')

@csrf_exempt
def edit_booked_hospital(request, booked_id):
    bookedHospital = get_object_or_404(HospitalBooking, id=booked_id)
    if request.method == "POST":
        current_hospital_id = str(bookedHospital.hospital_id)
        current_first_date_reserved = str(bookedHospital.first_date_reserved)
        current_first_date_from_reserved = str(bookedHospital.first_date_from_reserved)
        current_first_date_to_reserved = str(bookedHospital.first_date_to_reserved)
        current_insurance_type = bookedHospital.insurance_type

        hospital_id = request.POST.get('hospital')
        first_date_reserved = request.POST.get('appointment_date')
        first_date_from_reserved = request.POST.get('appointment_time_from')
        first_date_to_reserved = request.POST.get('appointment_time_to')
        insurance = request.POST.get('insurance')

        hospital = Hospital.objects.get(id=hospital_id)
        bookedHospital.hospital = hospital
        bookedHospital.first_date_reserved = first_date_reserved
        bookedHospital.first_date_from_reserved = first_date_from_reserved
        bookedHospital.first_date_to_reserved = first_date_to_reserved
        bookedHospital.insurance_type = insurance
        bookedHospital.save()

        hospital_changed = (current_hospital_id != hospital_id)
        first_date_changed = (current_first_date_reserved != first_date_reserved or current_first_date_from_reserved != first_date_from_reserved or current_first_date_to_reserved != first_date_to_reserved)
        insurance_changed = (current_insurance_type != insurance)


        current_language = get_language()
        home_url = request.build_absolute_uri(reverse('home'))
        hello_str = _("Hello Mr.") if bookedHospital.gender else _("Hello Ms.")

        hospital_url = request.build_absolute_uri(reverse('hospitalInfo', kwargs={'pk': bookedHospital.hospital.id}))
        google_maps_url = f"{bookedHospital.hospital.link_map}"
        timezone_str = TIMEZONE_DISPLAY.get(bookedHospital.hospital.timezone, 'UTC')
        formatted_date = parse_date(bookedHospital.first_date_reserved).strftime('%m/%d')

        hospital_display = f"<span style='font-weight:bold; color:black;'>{bookedHospital.hospital.name}</span>" if hospital_changed else bookedHospital.hospital.name
        visiting_time_displays = f"<span style='font-weight:bold;'>{bookedHospital.first_date_from_reserved}~{bookedHospital.first_date_to_reserved} on {formatted_date} ({timezone_str})</span>" if first_date_changed else f"{bookedHospital.first_date_from_reserved}~{bookedHospital.first_date_to_reserved} on {formatted_date} ({timezone_str})"


        if current_language == 'jp':
            insuranceSupport = ""
            if insurance == "cashless":
                insuranceSupport += f"こちらの病院では保険会社のキャッシュレス決済をご利用可能いただけます。病院へ行く際には、以下の3点をご用意ください。<br>1. パスポートまたは写真付き身分証明書<br>2. 保険証および保険証番号<br>3. 保険請求書 (お持ちの場合)<br><br>ご意見やご不明点がある場合は、どうぞお気軽に本メールへご返信くださいませ。<br><br>{bookedHospital.surname}様の早いご回復をお祈りしております。"
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            elif insurance == "insurance":
                insuranceSupport += f"こちらの病院では保険会社のキャッシュレス決済がご利用いただけません。一度、{bookedHospital.surname}様が立て替えていただき、のちに保険会社へ請求をする形になります。<br><br>保険会社の請求には診断書が必要になる為、必ず医師から受け取るようにしてください。<br><br><a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a><br><br>この度はご迷惑をおかけし、誠に申し訳ございませんでした。<br><br>ご理解のほどよろしくお願い申し上げます。"      
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            elif insurance == "not_insurance":
                insuranceSupport += f"{bookedHospital.surname}様の予約は以下の理由から、保険対象外になります。<br><br><a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a><br><br>この度はご迷惑をおかけし、誠に申し訳ございませんでした。<br><br>ご理解のほどよろしくお願い申し上げます。"
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            edit_email_content = f"""
<html>
<body>
    <p>{bookedHospital.firstname} {bookedHospital.surname} 様</p>
    <p>お世話になっております。</p>
    <p>株式会社Vitabiでございます。</p>
    <p>大変申し訳ありませんが、予約情報が変更されました。ご不便をおかけしますことを心よりお詫び申し上げます。</p>
    <p>以下はご予約の詳細です。（赤色で変更された情報を表示しています）</p>
    <ul>
        <li>病院名: <a href='{hospital_url}'>{hospital_display}</a></li>
        <li>住所: <a href='{google_maps_url}'>{bookedHospital.hospital.address}</a></li>
        <li>ご予約の時間: {visiting_time_displays}</li>
        <li>保険: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>保険証番号: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>症状: {bookedHospital.symptom}</li>
        <li>期間: {bookedHospital.duration}</li>
    </ul>
    {insurance_display}
    <a href='{home_url}'>ご質問や再予約に関してご支援が必要な場合は、本メールに返信するか、Vitabiから予約が可能です。</a>
    <p>この度はご迷惑をおかけし、誠に申し訳ございませんでした。</p>
    <p>ご理解のほどよろしくお願い申し上げます。</p>
    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""
        else:
            insuranceSupport = ""
            if insurance == "cashless":
                insuranceSupport += f"As this hospital supports Cashless Medical Service, please don't forget to bring the following items when visiting: <br> 1. Your passport or photo ID <br> 2. Your insurance document with policy number <br> 3. Insurance claim form (if you have one)"
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            elif insurance == "insurance" :
                insuranceSupport += f"We regret to inform you that our hospital does not currently support cashless medical services. Therefore, you will need to make out-of-pocket payments for any medical services received with medical certificate. Subsequently, you can file a claim with your insurance company for reimbursement."
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            elif insurance == "not_insurance":
                insuranceSupport += f"We regret to inform you that your insurance company does not support the coverage for your upcoming appointment [No Insurance Reason]. As a result, you will need to pay out of pocket for this service."
                insurance_display = f"<span style='font-weight:bold;'>{insuranceSupport}</span>" if insurance_changed else insuranceSupport
            edit_email_content = f"""
<html>
<body>
    <p>{hello_str} {bookedHospital.surname},</p>
    <p>{_("I hope this email finds you well. My name is Nhat Lieu, and I am the CEO of Vitabi.")}.</p>
    <p>{_("I am writing to inform you that your appointment information has recently been updated. Please find the details of the changes below: (modified info colored red)")}:</p>
    <ul>
        <li>Hospital: <a href='{hospital_url}'>{hospital_display}</a></li>
        <li>Address: <a href='{google_maps_url}'>{bookedHospital.hospital.address}</a></li>
        <li>Visiting Time: {visiting_time_displays}</li>
        <li>Insurance: {bookedHospital.insuranceCompany if bookedHospital.coverage == 'Others' else bookedHospital.coverage}</li>
        <li>Policy Number: {'' if bookedHospital.coverage == 'No Coverage' else bookedHospital.policyNumber}</li>
        <li>Symptom: {bookedHospital.symptom}</li>
        <li>Duration: {bookedHospital.duration}</li>
    </ul>
    {insurance_display}
    <p>{_("We apologize for any inconvenience this change may have caused.")}</p>
    <a href='{home_url}'>If you have any questions or require assistance with rescheduling, please do not hesitate to contact our support team by replying to this email or booking with Vitabi.</a>
    <p>{_("We wish you a speedy recovery.")}</p>
    <p>{_("Best regards,")}</p>
    <p>{_("Nhat Lieu")}<br>{_("CEO of Vitabi")}</p>
</body>
</html>
"""

        send_mail(
            _('Your Appointment Has Been Changed'),
            _('Please see the message in HTML format.'),
            'Vitabi <vitabi.info@gmail.com>',  
            [bookedHospital.email],  
            fail_silently=False,
            html_message=edit_email_content
        )
        return redirect('list_booked_hospital')
    return render(request, 'edit_booked_hospital.html', {'booking': bookedHospital})


@csrf_exempt
def delete_booked_hospital(request, booked_id):
    bookedHospital = get_object_or_404(HospitalBooking, id=booked_id)
    bookedHospital.delete()
    
    source = request.GET.get('source') 
    if source == 'booked':
        return redirect('care')
    else:
        return redirect('list_booked_hospital')

@csrf_exempt
def book1Page(request, hospital_id):
    if not request.session.get('selected_hospital_id'):
        return redirect('findHospital')
    
    if request.user.is_authenticated: 
        if HospitalBooking.objects.filter(user=request.user, status='waiting').exists():
            hospital_booking = HospitalBooking.objects.filter(user=request.user, status='waiting').first()
            if hospital_booking:
                request.session['hospitals_booking_id'] = hospital_booking.id
                messages.success(request, _('You have booked a hospital, please wait for a response.'))
                return redirect('hospitalInfo', pk=hospital_id)
        
    if request.user.is_authenticated:
        patient, created = Patient.objects.get_or_create(user=request.user) 
    else:
        patient = None
    hospital_id = request.session.get('selected_hospital_id')
    rejected_booking = None

    if 'rejected_booking_id' in request.session:
        rejected_booking = HospitalBooking.objects.get(id=request.session['rejected_booking_id'])
    
    if request.method == 'POST':
        check = False
        email_old = request.session.get('email_stored', '')
        email_new = request.POST.get('email', '')
        if email_old == email_new:
            check = True
        request.session['firstname'] = request.POST.get('firstname', '')
        request.session['firstname_stored'] = request.POST.get('firstname', '')
        request.session['firstname_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['surname'] = request.POST.get('surname', '')
        request.session['surname_stored'] = request.POST.get('surname', '')
        request.session['surname_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['gender'] = request.POST.get('gender', '')
        request.session['gender_stored'] = request.POST.get('gender', '')
        request.session['gender_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['dob'] = request.POST.get('dob', '')
        request.session['dob_stored'] = request.POST.get('dob', '')
        request.session['dob_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['email'] = request.POST.get('email', '')
        request.session['email_stored'] = request.POST.get('email', '')
        request.session['email_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['phone'] = request.POST.get('phone', '').replace('-', '')
        request.session['phone_stored'] = request.POST.get('phone', '').replace('-', '')
        request.session['phone_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')

        request.session['phone_country_code'] = request.POST.get('phone_country_code', '')
        request.session['phone_country_code_stored'] = request.POST.get('phone_country_code', '')
        request.session['phone_country_code_expired'] = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S.%f')
        if request.user.is_authenticated:
            if patient.email == request.POST.get('email', ''):
                return redirect('book3')
            else:
                return redirect('book2')
        else:
            if check:
                return redirect('book3')
            else:
                email = request.POST.get('email', '')
                getUser = User.objects.filter(email=email).first()
                if not getUser:
                    random_password = get_random_string(8)
                    user = User.objects.create_user(username=email, email=email, password=random_password)

                    user.first_name = request.POST.get('firstname', '') 
                    user.last_name = request.POST.get('surname', '')  
                    user.save()

                    patient = Patient.objects.create(
                        user=user,
                        firstname=request.POST.get('firstname', ''),
                        surname=request.POST.get('surname', ''),
                        gender=request.POST.get('gender', ''),
                        dob=request.POST.get('dob', ''),
                        email=email,
                        phone=request.POST.get('phone', ''),
                        phone_country_code=request.POST.get('phone_country_code', ''),
                        is_verified=False 
                    )
                return redirect('book2')
        
    
    context = {
        'firstname': rejected_booking.firstname if rejected_booking else (patient.firstname if patient else (request.session.get('firstname_stored', '') if request.session.get('firstname_stored', '') and request.session.get('firstname_expired', '') and datetime.strptime(request.session.get('firstname_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'surname': rejected_booking.surname if rejected_booking else (patient.surname if patient else (request.session.get('surname_stored', '') if request.session.get('surname_stored', '') and request.session.get('surname_expired', '') and datetime.strptime(request.session.get('surname_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'gender': rejected_booking.gender if rejected_booking else (patient.gender if patient else (request.session.get('gender_stored', '') if request.session.get('gender_stored', '') and request.session.get('gender_expired', '') and datetime.strptime(request.session.get('gender_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'dob': rejected_booking.dob.strftime('%Y-%m-%d') if rejected_booking else (patient.dob.strftime('%Y-%m-%d') if patient else (request.session.get('dob_stored', '') if request.session.get('dob_stored', '') and request.session.get('dob_expired', '') and datetime.strptime(request.session.get('dob_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')), 
        'email': rejected_booking.email if rejected_booking else (patient.email if patient else (request.session.get('email_stored', '') if request.session.get('email_stored', '') and request.session.get('email_expired', '') and datetime.strptime(request.session.get('email_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'phone': rejected_booking.phone if rejected_booking else (patient.phone if patient else (request.session.get('phone_stored', '') if request.session.get('phone_stored', '') and request.session.get('phone_expired', '') and datetime.strptime(request.session.get('phone_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'phone_country_code': rejected_booking.phone_country_code if rejected_booking else (patient.phone_country_code if patient else (request.session.get('phone_country_code_stored', '') if request.session.get('phone_country_code_stored', '') and request.session.get('phone_country_code_expired', '') and datetime.strptime(request.session.get('phone_country_code_expired', ''), '%Y-%m-%d %H:%M:%S.%f') > datetime.now() else '')),
        'hospital_id': hospital_id,
        'current_language': get_language(),
    }
    return render(request, 'home/book1.html', context)

@csrf_exempt
def book3Page(request):
    if not request.session.get('firstname', '') or not request.session.get('surname', ''):
        return redirect('findHospital')
    
    hospital_id = request.session.get('selected_hospital_id')
    if hospital_id:
        hospital = Hospital.objects.get(id=hospital_id)
    else:
        context = {'error': _('No hospital selected. Please select a hospital first.')}
        return render(request, 'home/book3.html', context)
    
    rejected_booking = None

    if request.method == 'POST':
        request.session['hospital_id'] = hospital_id
        firstdate_str = request.POST.get('firstdate', '')
        firstdatefrom_str = request.POST.get('firstdatefrom', '')
        firstdateto_str = request.POST.get('firstdateto', '')
        seconddate_str = request.POST.get('seconddate', '')
        seconddatefrom_str = request.POST.get('seconddatefrom', '')
        seconddateto_str = request.POST.get('seconddateto', '')
        request.session['firstdate'] = firstdate_str
        request.session['firstdatefrom'] = firstdatefrom_str
        request.session['firstdateto'] = firstdateto_str
        request.session['seconddate'] = seconddate_str
        request.session['seconddatefrom'] = seconddatefrom_str
        request.session['seconddateto'] = seconddateto_str
        request.session['symptom'] = request.POST.get('symptom', '')
        request.session['duration'] = request.POST.get('duration', '')

        firstdate_day = None
        seconddate_day = None
        error_message1 = None
        error_message2 = None
        error_message3 = None
        error_message4 = None
        error_message5 = None
        error_message6 = None
        error_message7 = None
        error_message8 = None
        error_message9 = None
        working_hours = None
        current_datetime = datetime.now()

        if firstdate_str:
            firstdate_obj = datetime.strptime(firstdate_str, '%Y-%m-%d')
            firstdatefrom_obj = datetime.strptime(firstdatefrom_str, '%H:%M').time()
            firstdateto_obj = datetime.strptime(firstdateto_str, '%H:%M').time()
            firstdatetime_from = datetime.combine(firstdate_obj, firstdatefrom_obj)
            firstdatetime_to = datetime.combine(firstdate_obj, firstdateto_obj)
            firstdate_day = firstdate_obj.strftime('%A')

            if firstdatetime_from < current_datetime or firstdatetime_to < current_datetime:
                error_message1 = _("Please select a time in the future")

            if firstdatetime_to - firstdatetime_from < timedelta(hours=2):
                error_message4 = _("End time must be at least 2 hours later.")

            working_hours = WorkingHours.objects.filter(hospital=hospital, day_of_week=firstdate_day)
            time_is_valid = False
            for interval in working_hours:
                if (interval.open_time <= firstdatefrom_obj <= interval.close_time and
                    interval.open_time <= firstdateto_obj <= interval.close_time):
                    time_is_valid = True
                    break
            if not time_is_valid:
                error_message5 = _("Please select a time when the hospital is open!")

        if not error_message1 and seconddate_str:
            seconddate_obj = datetime.strptime(seconddate_str, '%Y-%m-%d')
            seconddatefrom_obj = datetime.strptime(seconddatefrom_str, '%H:%M').time()
            seconddateto_obj = datetime.strptime(seconddateto_str, '%H:%M').time()
            seconddatetime_from = datetime.combine(seconddate_obj, seconddatefrom_obj)
            seconddatetime_to = datetime.combine(seconddate_obj, seconddateto_obj)
            seconddate_day = seconddate_obj.strftime('%A')

            if seconddatetime_from < current_datetime or seconddatetime_to < current_datetime:
                error_message2 = _("Please select a time in the future")

            if seconddatetime_to - seconddatetime_from < timedelta(hours=2):
                error_message6 = _("End time must be at least 2 hours later.")

            working_hours = WorkingHours.objects.filter(hospital=hospital, day_of_week=seconddate_day)
            time_is_valid = False
            for interval in working_hours:
                if (interval.open_time <= seconddatefrom_obj <= interval.close_time and
                    interval.open_time <= seconddateto_obj <= interval.close_time):
                    time_is_valid = True
                    break
            if not time_is_valid:
                error_message7 = _("Please select a time when the hospital is open!")
 
        if not error_message1 and not error_message2 and not error_message4 and not error_message5 and not error_message6 and not error_message7 and working_hours:
            return redirect('book4')

        working_hours = list(WorkingHours.objects.filter(hospital=hospital))
        days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        working_hours_dict = defaultdict(list)
        for hours in working_hours:
            time_range = f"{hours.open_time.strftime('%H:%M')} - {hours.close_time.strftime('%H:%M')}"
            working_hours_dict[hours.day_of_week].append(time_range)

        formatted_working_hours = []
        for day in days_order:
            if working_hours_dict.get(day):
                times = working_hours_dict[day]
                formatted_working_hours.append({
                    'day': _(day),
                    'time': ' / '.join(times)
                })

        if 'Sunday' not in working_hours_dict:
            formatted_working_hours.append({'day': _('Sunday'), 'time': _('Closed')})

        if 'rejected_booking_id' in request.session:
            rejected_booking = HospitalBooking.objects.get(id=request.session['rejected_booking_id'])
                
        context = {
            'firstdate': rejected_booking.first_date if rejected_booking else firstdate_str,
            'firstdatefrom': rejected_booking.first_date_from if rejected_booking else firstdatefrom_str,
            'firstdateto': rejected_booking.first_date_to if rejected_booking else firstdateto_str,
            'seconddate': rejected_booking.second_date if rejected_booking else seconddate_str,
            'seconddatefrom': rejected_booking.second_date_from if rejected_booking else seconddatefrom_str,
            'seconddateto': rejected_booking.second_date_to if rejected_booking else seconddateto_str,
            'symptom': rejected_booking.symptom if rejected_booking else request.session.get('symptom', ''),
            'duration': rejected_booking.duration if rejected_booking else request.session.get('duration', ''),
            'hospital': hospital,
            'error_message1': error_message1,
            'error_message2': error_message2,
            'error_message3': error_message3,
            'error_message4': error_message4,
            'error_message5': error_message5,
            'error_message6': error_message6,
            'error_message7': error_message7,
            'error_message8': error_message8,
            'error_message9': error_message9,
            'formatted_working_hours': formatted_working_hours,
            'hospital_id': hospital_id,
        }

        return render(request, 'home/book3.html', context)
    
    working_hours = list(WorkingHours.objects.filter(hospital=hospital))
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    working_hours_dict = defaultdict(list)
    for hours in working_hours:
        time_range = f"{hours.open_time.strftime('%H:%M')} - {hours.close_time.strftime('%H:%M')}"
        working_hours_dict[hours.day_of_week].append(time_range)

    formatted_working_hours = []
    for day in days_order:
        if working_hours_dict.get(day):
            times = working_hours_dict[day]
            formatted_working_hours.append({
                'day': _(day),
                'time': ' / '.join(times)
            })

    if 'Sunday' not in working_hours_dict:
        formatted_working_hours.append({'day': _('Sunday'), 'time': _('Closed')})

    if 'rejected_booking_id' in request.session:
        rejected_booking = HospitalBooking.objects.get(id=request.session['rejected_booking_id'])

    context = {
        'firstdate': rejected_booking.first_date if rejected_booking else request.session.get('firstdate', ''),
        'firstdatefrom': rejected_booking.first_date_from if rejected_booking else request.session.get('firstdatefrom', ''),
        'firstdateto': rejected_booking.first_date_to if rejected_booking else request.session.get('firstdateto', ''),
        'seconddate': rejected_booking.second_date if rejected_booking else request.session.get('seconddate', ''),
        'seconddatefrom': rejected_booking.second_date_from if rejected_booking else request.session.get('seconddatefrom', ''),
        'seconddateto': rejected_booking.second_date_to if rejected_booking else request.session.get('seconddateto', ''),
        'symptom': rejected_booking.symptom if rejected_booking else request.session.get('symptom', ''),
        'duration': rejected_booking.duration if rejected_booking else request.session.get('duration', ''),
        'hospital': hospital,
        'formatted_working_hours': formatted_working_hours,
        'hospital_id': hospital_id,
    }

    return render(request, 'home/book3.html', context)

@csrf_exempt
def insurance(request):
    insurance_info = InsuranceInfo.objects.filter(user=request.user)
    for info in insurance_info:
        coverage = _(info.coverage)
    context = {
        'insurance_info': insurance_info,
        'coverage': coverage,
    }
    return render(request, 'home/insurance.html', context)

@csrf_exempt
def book4Page(request):
    if not request.session.get('firstdate', ''):
        return redirect('findHospital')
    rejected_booking = None
    
    if request.method == 'POST':
        request.session['coverage'] = request.POST.get('coverage', '')
        if request.session['coverage'] == "No coverage":
            request.session['insuranceCompany'] = ""
            request.session['policyNumber'] = ""
        else:
            if request.session['coverage'] == "Others" or request.session['coverage'] == "Khác":
                request.session['insuranceCompany'] = request.POST.get('insuranceCompany', '')
            else:
                request.session['insuranceCompany'] = ""
            request.session['policyNumber'] = request.POST.get('policyNumber', '')
        return redirect('book5')
    
    
    
    hospital_id = request.session.get('selected_hospital_id')

    display_coverage = _(request.session.get('coverage', ''))
    if request.user.is_authenticated:
        insurance_info = InsuranceInfo.objects.get(user=request.user)
        insurance_infos = InsuranceInfo.objects.filter(user=request.user)

        translated_insurance_info = [(info.id, _(info.coverage)) for info in insurance_infos]

    if 'rejected_booking_id' in request.session:
        rejected_booking = HospitalBooking.objects.get(id=request.session['rejected_booking_id'])

    context = {
        'current_coverage': rejected_booking.coverage if rejected_booking else _(insurance_info.coverage) if request.user.is_authenticated else '',

        'coverage': display_coverage,
        'coverage1': request.session.get('coverage', '') if request.session.get('coverage', '') else display_coverage,

        'insuranceCompany': rejected_booking.insuranceCompany if rejected_booking else request.session.get('insuranceCompany', ''),
        'policyNumber': rejected_booking.policyNumber if rejected_booking else request.session.get('policyNumber', ''),

        'insurance_infos': insurance_infos if request.user.is_authenticated else '',
        'insurance_info_translated': translated_insurance_info if request.user.is_authenticated else '',
        'insurance_info_code': insurance_info if request.user.is_authenticated else '',

        'hospital_id': hospital_id,
    }

    return render(request, 'home/book4.html', context)

import base64
def create_token_for_booking(booking):
    token = get_random_string(32)
    booking.token = base64.urlsafe_b64encode(token.encode()).decode()
    booking.save()
    return booking.token

from django.urls import reverse
from django.utils.crypto import get_random_string
@csrf_exempt
def book5Page(request):
    if not request.session.get('coverage', ''):
        return redirect('findHospital')
    
    utm_source = request.session.get('utm_source', '')
    firstname = request.session.get('firstname', '')
    surname = request.session.get('surname', '')
    gender = request.session.get('gender', '')
    dob = request.session.get('dob', '')
    email = request.session.get('email', '')
    phone = request.session.get('phone', '') # 0814742238
    
    phone = phone.lstrip('0')    # 814742238
    phone_country_code = request.session.get('phone_country_code') # +84
    phone_country_code = phone_country_code + '-' # +84-
    full_phone = phone_country_code + phone # +84-814742238

    firstdate = request.session.get('firstdate', '')
    firstdatefrom = request.session.get('firstdatefrom', '')
    firstdateto = request.session.get('firstdateto', '')
    seconddate = request.session.get('seconddate', '')
    seconddatefrom = request.session.get('seconddatefrom', '')
    seconddateto = request.session.get('seconddateto', '')
    symptom = request.session.get('symptom', '')
    duration = request.session.get('duration', '')
    moreinfo = f"{symptom} - {duration}"

    coverage = request.session.get('coverage', '')
    insuranceCompany = request.session.get('insuranceCompany', '')
    policyNumber = request.session.get('policyNumber', '')

    hospital = None 
    hospital_id = request.session.get('hospital_id')
    if hospital_id:
        hospital = Hospital.objects.get(id=hospital_id)

    timezone_str = TIMEZONE_DISPLAY.get(hospital.timezone, 'UTC')

    if request.method == 'POST':
        email = request.session.get('email', '')
            
        if not Patient.objects.filter(email=email, is_verified=True).exists():
            user = User.objects.get(email=email)

            user.first_name = firstname
            user.last_name = surname
            user.save()

            patient, created = Patient.objects.get_or_create(email=email)
            patient.firstname = firstname
            patient.surname = surname
            patient.gender = gender
            patient.dob = dob
            patient.phone = phone
            patient.phone_country_code = phone_country_code.rstrip('-')
            patient.user = user
            patient.is_verified = True
            patient.save()

            gender_str = _("Male") if gender else _("Female")
            hello_str = _("Hello Mr.") if gender else _("Hello Ms.")

            firstdate_formatted = datetime.strptime(firstdate, '%Y-%m-%d').strftime('%m/%d') if firstdate else ''
            firstdate_time = f"{firstdatefrom}~{firstdateto} on {firstdate_formatted} ({timezone_str})" if firstdatefrom and firstdateto else ''

            seconddate_formatted = datetime.strptime(seconddate, '%Y-%m-%d').strftime('%m/%d') if seconddate else ''
            seconddate_time = f"{seconddatefrom}~{seconddateto} on {seconddate_formatted} ({timezone_str})" if seconddatefrom and seconddateto else ''

            dates_info1 = ""
            dates_info2 = ""
            if firstdate or firstdatefrom or firstdateto:
                dates_info1 += f"<li> {_('1st Preferred Date/Times')}: {firstdate_time} </li>"
            if seconddate or seconddatefrom or seconddateto:
                dates_info2 += f"<li> {_('2nd Preferred Date/Times')}: {seconddate_time} </li>"


            dob_formatted = datetime.strptime(dob, '%Y-%m-%d').strftime('%Y/%m/%d') if dob else _('N/A')

            insurance_display = insuranceCompany if coverage == "Others" else _(coverage)

            policy_display = policyNumber if coverage.lower() != "no coverage" else _("N/A")

            if hospital:
                hospital_url = request.build_absolute_uri(reverse('hospitalInfo', kwargs={'pk': hospital.id}))
                hospital_info = f"<a href='{hospital_url}'>{hospital.name}</a>"
            else:
                hospital_info = _('N/A')

            InsuranceInfo.objects.create(
                user=user,
                coverage=coverage,
                insurance_company=insuranceCompany,
                policy_number=policyNumber
            )

            booking = HospitalBooking.objects.create(
                user=user,
                firstname=firstname,
                surname=surname,
                gender=gender,
                dob=dob,
                email=email,
                phone=full_phone,
                phone_country_code=phone_country_code,
                hospital=hospital,
                first_date=firstdate,
                first_date_from=firstdatefrom,
                first_date_to=firstdateto,
                second_date=seconddate if seconddate else None,
                second_date_from=seconddatefrom if seconddatefrom else None,
                second_date_to=seconddateto if seconddateto else None,
                more_info=moreinfo,
                symptom=symptom,
                duration=duration,
                coverage=coverage,
                insuranceCompany=insuranceCompany,
                policyNumber=policyNumber,
                utm_source=utm_source
            )

            booking_detail_url = request.build_absolute_uri(reverse('bookedHospitalDetail', kwargs={'pk': booking.pk}))

            token = create_token_for_booking(booking)

            current_language = get_language()

            if current_language == 'jp':

                html_email_content = f"""
<html>
<body>
    <p>{user.last_name}{user.first_name} 様</p>
    <p>この度はVitabi（バイタビ）にご登録いただき、誠にありがとうございます！アカウントが正常に作成されました。以下にログイン情報をお知らせします：</p>
    <ul>
        <li>メールアドレス: {email}</li>
        <li>パスワード: {user.password}</li>
    </ul>
    <p>予約情報をご確認いただくには、以下のリンクをクリックしてください。</p>
    <a href="{request.build_absolute_uri(reverse('bookedHospitalDetail', kwargs={'pk': booking.pk}))}?token={token}">予約情報を見る</a>
    <p>もしこのアカウント登録に心当たりがない場合は、直ちに弊社サポートチームまでご連絡ください。</p>
    <p>Vitabiをご利用いただけることを楽しみにしております！</p>
    <p>よろしくお願いいたします。</p>
    <p>Vitabiチーム</p>
</body>
</html>
"""
                html_email_content_booking = f"""
<html>
<body>
    <p>{surname} {firstname} 様</p>
    <p>株式会社Vitabiでございます。</p>
    <p>本メールは、Vitabiを通じて病院の予約を行ったユーザーに向けて自動送信される確認メールです。</p>
    <p>下記は、ご予約の際に{surname}様から提供いただいた情報です。</p>
    <ul>
        <li>名前: {firstname} {surname}</li>
        <li>性別: {gender_str}</li>
        <li>生年月日: {dob_formatted}</li>
        <li>メールアドレス: {email}</li>
        <li>電話番号: {phone_country_code}{phone}</li>
        <li>選択した病院: {hospital_info}</li>
        <li>第1希望日時: {firstdate_time}</li>\
        {dates_info2}
        <li>保険: {insurance_display}</li>
        <li>保険証番号: {policy_display}</li>
        <li>症状: {symptom}</li>
        <li>期間: {duration}</li>
    </ul>
    <p>まだ予約は完了していません。現在、ご希望の日時と場所で予約を処理中です。予約が確定次第、追ってご連絡いたします。</p>
    <p><a href="{booking_detail_url}">誤って病院を予約してした場合は、こちらからキャンセル手続きが可能です。</a></p>
    <p>ご意見やご不明点がある場合は、どうぞお気軽に本メールへご返信くださいませ。</p>
    <p>改めてこの度はVitabiをご利用いただき、ありがとうございます!</p>
    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""     
            else:
                html_email_content = f"""
<html>
<body>
    <p>Subject: Welcome to Vitabi – Your Account Details</p>
    <p>Dear Mr./Ms. {user.last_name},</p>
    <p>Thank you for registering with Vitabi! Your account has been successfully created. Below are your login details:</p>
    <ul>
        <li>Email: {email}</li>
        <li>Temporary Password: {user.password}</li>
    </ul>
    <p>To view your booking information, please click the link below:</p>
    <a href="{request.build_absolute_uri(reverse('bookedHospitalDetail', kwargs={'pk': booking.pk}))}?token={token}">View Booking Information</a>
    <p>If you did not register this account, please contact our support team immediately for assistance.</p>
    <p>We’re thrilled to have you on board and look forward to serving you!</p>
    <p>Best regards,</p>
    <p>The Vitabi Team</p>
</body>
</html>
"""
                html_email_content_booking = f"""
<html>
<body>
    <p>{hello_str} {surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("This is an automatically sent acknowledgment email for users who have just booked a hospital appointment via Vitabi")}.</p>

    <p>{_("Here is the information you have provided")}:</p>

    <ul>
    <li>{_("Name")}: {firstname} {surname}</li>
    <li>{_("Gender")}: {gender_str}</li>
    <li>{_("Date of Birth")}: {dob_formatted}</li>
    <li>{_("Email")}: {email}</li>
    <li>{_("Phone Number")}: {phone_country_code}{phone}</li>
    <li>{_("Selected Hospital")}: {hospital_info}</li>
    {dates_info1}
    {dates_info2}
    <li>{_("Insurance")}: {insurance_display}</li>
    <li>{_("Policy Number")}: {policy_display}</li>
    <li>{_("Symptom")}: {symptom}</li>
    <li>{_("Duration")}: {duration}</li>
    </ul>
    
    <p>{_("Please be aware that your booking is not yet complete. We are processing your appointment request with your preferred time and place. We will notify you as soon as your booking is approved.")}</p>

    <p>{_("If you want to cancel your booking, please click")} <a href="{booking_detail_url}">{_("here")}</a>.</p>
    
    <p>{_("Thank you for booking with us! We welcome any of your feedback. If you have any questions or feedback, please feel free to reply to this message.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_('Nhat Lieu')}<br>{_('CEO of Vitabi')}</p>
</body>
</html>
"""

            send_mail(
                _('Welcome to Vitabi – Your Account Details'),
                'Please see the message in HTML format.',
                'Vitabi <vitabi.info@gmail.com>',
                [email],
                fail_silently=False,
                html_message=html_email_content
            ) 

            send_mail(
                _('Appointment Request Received'),
                _('Please see the message in HTML format.'),
                'Vitabi <vitabi.info@gmail.com>',
                [email],
                fail_silently=False,
                html_message=html_email_content_booking
            )

            # Gửi email về hệ thống
            system_email_content = f"""
<html>
<body>
    <p>{_("A new appointment has been made by")} {firstname} {surname}.</p>

    <p>{_("Here is the information provided by the user")}:</p>

    <ul>
    <li>{_("Name")}: {firstname} {surname}</li>
    <li>{_("Gender")}: {gender_str}</li>
    <li>{_("Date of Birth")}: {dob_formatted}</li>
    <li>{_("Email")}: {email}</li>
    <li>{_("Phone Number")}: {phone_country_code}{phone}</li>
    <li>{_("Selected Hospital")}: {hospital_info}</li>
    {dates_info1}
    {dates_info2}
    <li>{_("Insurance")}: {insurance_display}</li>
    <li>{_("Policy Number")}: {policy_display}</li>
    <li>{_("Symptom")}: {symptom}</li>
    <li>{_("Duration")}: {duration}</li>
    </ul>
    
    <p>{_("Please follow up with the hospital and confirm the appointment.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_('Nhat Lieu')}<br>{_('CEO of Vitabi')}</p>
</body>
</html>
"""
                
            send_mail(
                _('New Appointment Made from %(firstname)s %(surname)s') % {'firstname': firstname, 'surname': surname},
                _('Please see the message in HTML format.'),
                'Vitabi <vitabi.info@gmail.com>',
                ['vitabi.info@gmail.com'], 
                fail_silently=False,
                html_message=system_email_content 
            )

            login(request, user)

            request.session.pop('firstname_stored', None)
            request.session.pop('surname_stored', None)
            request.session.pop('gender_stored', None)
            request.session.pop('dob_stored', None)
            request.session.pop('email_stored', None)
            request.session.pop('phone_stored', None)
            request.session.pop('phone_country_code_stored', None)

            messages.success(request, _('Successfully Booked'))

            return redirect('home')
        
        else:
            user = User.objects.get(email=email)
            gender_str = _("Male") if gender else _("Female")
            hello_str = _("Hello Mr.") if gender else _("Hello Ms.")

            firstdate_formatted = datetime.strptime(firstdate, '%Y-%m-%d').strftime('%m/%d') if firstdate else ''
            firstdate_time = f"{firstdatefrom}~{firstdateto} on {firstdate_formatted} ({timezone_str})" if firstdatefrom and firstdateto else ''

            seconddate_formatted = datetime.strptime(seconddate, '%Y-%m-%d').strftime('%m/%d') if seconddate else ''
            seconddate_time = f"{seconddatefrom}~{seconddateto} on {seconddate_formatted} ({timezone_str})" if seconddatefrom and seconddateto else ''

            dates_info1 = ""
            dates_info2 = ""
            if firstdate or firstdatefrom or firstdateto:
                dates_info1 += f"<li> {_('1st Preferred Date/Times')}: {firstdate_time} </li>"
            if seconddate or seconddatefrom or seconddateto:
                dates_info2 += f"<li> {_('2nd Preferred Date/Times')}: {seconddate_time} </li>"


            dob_formatted = datetime.strptime(dob, '%Y-%m-%d').strftime('%Y/%m/%d') if dob else _('N/A')

            insurance_display = insuranceCompany if coverage == "Others" else _(coverage)

            policy_display = policyNumber if coverage.lower() != "no coverage" else _("N/A")

            if hospital:
                hospital_url = request.build_absolute_uri(reverse('hospitalInfo', kwargs={'pk': hospital.id}))
                hospital_info = f"<a href='{hospital_url}'>{hospital.name}</a>"
            else:
                hospital_info = _('N/A')

            booking = HospitalBooking.objects.create(
                user=user,
                firstname=firstname,
                surname=surname,
                gender=gender,
                dob=dob,
                email=email,
                phone=full_phone,
                phone_country_code=phone_country_code,
                hospital=hospital,
                first_date=firstdate,
                first_date_from=firstdatefrom,
                first_date_to=firstdateto,
                second_date=seconddate if seconddate else None,
                second_date_from=seconddatefrom if seconddatefrom else None,
                second_date_to=seconddateto if seconddateto else None,
                more_info=moreinfo,
                symptom=symptom,
                duration=duration,
                coverage=coverage,
                insuranceCompany=insuranceCompany,
                policyNumber=policyNumber,
                utm_source=utm_source 
            )

            booking_detail_url = request.build_absolute_uri(reverse('bookedHospitalDetail', kwargs={'pk': booking.pk}))

            current_language = get_language()

            if current_language == 'jp':
                html_email_content = f"""
<html>
<body>
    <p>{surname} {firstname} 様</p>
    <p>株式会社Vitabiでございます。</p>
    <p>本メールは、Vitabiを通じて病院の予約を行ったユーザーに向けて自動送信される確認メールです。</p>
    <p>下記は、ご予約の際に{surname}様から提供いただいた情報です。</p>
    <ul>
        <li>名前: {firstname} {surname}</li>
        <li>性別: {gender_str}</li>
        <li>生年月日: {dob_formatted}</li>
        <li>メールアドレス: {email}</li>
        <li>電話番号: {phone_country_code}{phone}</li>
        <li>選択した病院: {hospital_info}</li>
        <li>第1希望日時: {firstdate_time}</li>\
        {dates_info2}
        <li>保険: {insurance_display}</li>
        <li>保険証番号: {policy_display}</li>
        <li>症状: {symptom}</li>
        <li>期間: {duration}</li>
    </ul>
    <p>まだ予約は完了していません。現在、ご希望の日時と場所で予約を処理中です。予約が確定次第、追ってご連絡いたします。</p>
    <p><a href="{booking_detail_url}">誤って病院を予約してした場合は、こちらからキャンセル手続きが可能です。</a></p>
    <p>ご意見やご不明点がある場合は、どうぞお気軽に本メールへご返信くださいませ。</p>
    <p>改めてこの度はVitabiをご利用いただき、ありがとうございます!</p>
    <p>Nhat Lieu<br>株式会社Vitabi 代表取締役</p>
</body>
</html>
"""    
            else:
                html_email_content = f"""
<html>
<body>
    <p>{hello_str} {surname},</p>

    <p>{_("I'm Nhat, CEO of Vitabi")}.</p>

    <p>{_("This is an automatically sent acknowledgment email for users who have just booked a hospital appointment via Vitabi")}.</p>

    <p>{_("Here is the information you have provided")}:</p>

    <ul>
    <li>{_("Name")}: {firstname} {surname}</li>
    <li>{_("Gender")}: {gender_str}</li>
    <li>{_("Date of Birth")}: {dob_formatted}</li>
    <li>{_("Email")}: {email}</li>
    <li>{_("Phone Number")}: {phone_country_code}{phone}</li>
    <li>{_("Selected Hospital")}: {hospital_info}</li>
    {dates_info1}
    {dates_info2}
    <li>{_("Insurance")}: {insurance_display}</li>
    <li>{_("Policy Number")}: {policy_display}</li>
    <li>{_("Symptom")}: {symptom}</li>
    <li>{_("Duration")}: {duration}</li>
    </ul>
    
    <p>{_("Please be aware that your booking is not yet complete. We are processing your appointment request with your preferred time and place. We will notify you as soon as your booking is approved.")}</p>

    <p>{_("If you want to cancel your booking, please click")} <a href="{booking_detail_url}">{_("here")}</a>.</p>
    
    <p>{_("Thank you for booking with us! We welcome any of your feedback. If you have any questions or feedback, please feel free to reply to this message.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_('Nhat Lieu')}<br>{_('CEO of Vitabi')}</p>
</body>
</html>
"""
                

            send_mail(
                _('Appointment Request Received'),
                _('Please see the message in HTML format.'),
                'Vitabi <vitabi.info@gmail.com>',
                [email],
                fail_silently=False,
                html_message=html_email_content 
            )

            # Gửi email về hệ thống
            system_email_content = f"""
<html>
<body>
    <p>{_("A new appointment has been made by")} {firstname} {surname}.</p>

    <p>{_("Here is the information provided by the user")}:</p>

    <ul>
    <li>{_("Name")}: {firstname} {surname}</li>
    <li>{_("Gender")}: {gender_str}</li>
    <li>{_("Date of Birth")}: {dob_formatted}</li>
    <li>{_("Email")}: {email}</li>
    <li>{_("Phone Number")}: {phone_country_code}{phone}</li>
    <li>{_("Selected Hospital")}: {hospital_info}</li>
    {dates_info1}
    {dates_info2}
    <li>{_("Insurance")}: {insurance_display}</li>
    <li>{_("Policy Number")}: {policy_display}</li>
    <li>{_("Symptom")}: {symptom}</li>
    <li>{_("Duration")}: {duration}</li>
    </ul>
    
    <p>{_("Please follow up with the hospital and confirm the appointment.")}</p>

    <p>{_("Best regards,")}</p>

    <p>{_('Nhat Lieu')}<br>{_('CEO of Vitabi')}</p>
</body>
</html>
"""
                
            send_mail(
                _('New Appointment Made from %(firstname)s %(surname)s') % {'firstname': firstname, 'surname': surname},
                _('Please see the message in HTML format.'),
                'Vitabi <vitabi.info@gmail.com>',
                ['vitabi.info@gmail.com'], 
                fail_silently=False,
                html_message=system_email_content 
            )

            InsuranceInfo.objects.filter(user=user).delete()

            
            InsuranceInfo.objects.create(
                user=user,
                coverage=coverage,
                insurance_company=insuranceCompany,
                policy_number=policyNumber
            )

            login(request, user)

            messages.success(request, _('Successfully Booked'))

            return redirect('home')

    context = {
        'firstname': firstname,
        'surname': surname,
        'gender': gender,
        'dob': dob,
        'email': email,
        'phone': phone,
        'phone_country_code': phone_country_code,

        'hospital': hospital,
        'firstdate': firstdate,
        'firstdatefrom': firstdatefrom,
        'firstdateto': firstdateto,
        'seconddate': seconddate,
        'seconddatefrom': seconddatefrom,
        'seconddateto': seconddateto,
        'moreinfo': moreinfo,
        'duration': duration,
        'symptom': symptom,

        'coverage': _(coverage),
        'insuranceCompany': insuranceCompany,
        'policyNumber': policyNumber,
        'hospital_id': hospital_id,
    }

    return render(request, 'home/book5.html', context)

@csrf_exempt
def carePage(request):
    status_filter = request.GET.get('status')
    if status_filter in ['approved', 'rejected', 'waiting']:
        hospital_booking = HospitalBooking.objects.filter(
            user=request.user, status=status_filter
        ).order_by('hospital__country', '-created_at')
    else:
        if request.user.is_authenticated:
            hospital_booking = HospitalBooking.objects.filter(
                user=request.user
            ).order_by('hospital__country', '-created_at')
        else:
            hospital_booking = None

    grouped_bookings = defaultdict(lambda: defaultdict(list))
    if hospital_booking:
        for booking in hospital_booking:
            country_code = booking.hospital.country
            booking_date = booking.created_at.date()
            grouped_bookings[country_code][booking_date].append(booking)

    context = {
        'grouped_bookings': {k: dict(v) for k, v in grouped_bookings.items()},
        'selected_status': status_filter,
        'current_language': get_language(),
        'MEDIA_URL': settings.MEDIA_URL,
    }
    return render(request, 'home/care.html', context)

@csrf_exempt
def loginPage(request):
    if request.user.is_authenticated:
        next_url = request.GET.get('next', 'home')
        return redirect(next_url)
    
    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')
        next_url = request.POST.get('next', 'home')
        
        try:
            user = User.objects.get(username=email)
        except:
            messages.info(request, _('Email or password does not valid'), extra_tags='userError')
            request.session['email'] = email
            return redirect('login')
        
        user = authenticate(request, username=email, password=password)   
        
        if user is not None:
            login(request, user)
            return redirect(next_url if next_url else "home")
        else:
            messages.info(request, _('Email or password does not valid'), extra_tags='userError')
            request.session['email'] = email
            return redirect('login')

    context = {
        'email': request.session.get('email', ''),
        'current_language': get_language(),
        'MEDIA_URL': settings.MEDIA_URL,
    }

    return render(request, 'account/login.html', context)

from django.http import JsonResponse

# @csrf_exempt
# def modalLogin(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             email = data.get('email')
#             password = data.get('password')
            
#             try:
#                 user = User.objects.get(username=email)
#             except User.DoesNotExist:
#                 return JsonResponse({'success': False, 'message': _('Email or password does not valid')})
            
#             user = authenticate(request, username=email, password=password)   
            
#             if user is not None:
#                 login(request, user)
#                 return JsonResponse({'success': True})
#             else:
#                 return JsonResponse({'success': False, 'message': _('Email or password does not valid')})
#         except json.JSONDecodeError:
#             return JsonResponse({'success': False, 'message': _('Invalid JSON')})
#     return JsonResponse({'success': False, 'message': _('Invalid request method')})

@csrf_exempt
def logoutPage(request):
    logout(request)
    return redirect('home')

@csrf_exempt
def generate_verification_code_register(request):
    return ''.join(random.choices(string.digits, k=5))

@csrf_exempt
def registerPage(request):
    request.session.pop('email', None)
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        repassword = request.POST.get('repassword')
        request.session['next_url'] = request.GET.get('next', 'home')

        if password == repassword:
            if User.objects.filter(email=email).exists() and Patient.objects.filter(email=email, is_verified=True).exists():
                messages.info(request, _('Email already existed'), extra_tags='emailExist')
                return redirect('register')
            else:
                request.session['email'] = email
                request.session['password'] = password
                return redirect('register1')
        else:
            messages.info(request, _('Passwords do not match'), extra_tags='repass')

    context = {
        'email': request.session.get('email', '')
    }

    return render(request, 'account/signup.html', context)

@csrf_exempt
def register1Page(request):
    if not request.session.get('email', ''):
        return redirect('register')
    
    verification_code = generate_verification_code_register(request)
    request.session['verification_code'] = verification_code 
    email = request.session.get('email', '')

    send_mail(
        _('Your Verification Code'),
        f'{_("Your verification code is")}: {verification_code}',
        'Vitabi <vitabi.info@gmail.com>',
        [email],
        fail_silently=False,
    )
    return render(request, 'account/signup1.html')

@csrf_exempt
def verify_account_register(request):
    if request.method == 'POST':
        email = request.session.get('email', '')
        new_email = request.session.get('new_email', '')
        entered_code = ''.join(request.POST.get('digit-{}'.format(i), '') for i in range(1, 6))
        if entered_code == request.session.get('verification_code'):
            if new_email:
                patient_profile = request.user.patient
                patient_profile.email = new_email
                patient_profile.save()
                request.user.username = new_email 
                request.user.email = new_email 
                request.user.save() 
                return redirect('personal')
            return redirect('register2') if email else redirect('personal')
        else:
            messages.info(request, _('The verification code is incorrect. Please try again.'), extra_tags='invalidCode')

    return render(request, 'account/signup1.html')

@csrf_exempt
def resend_verification_code_register(request):
    verification_code = generate_verification_code()
    request.session['verification_code'] = verification_code
    email = request.session.get('email', '')
    new_email = request.session.get('new_email', '')
    
    send_mail(
        _('Your Verification Code'),
        f'{_("Your new verification code is")}: {verification_code}',
        'Vitabi <vitabi.info@gmail.com>',
        [email] if email else [new_email],
        fail_silently=False,
    )
    
    messages.info(request, _('A new verification code has been sent to your email.'), extra_tags='resetCode')
    return render(request, 'account/signup1.html')

@csrf_exempt
def register2Page(request):
    if not request.session.get('email', ''):
        return redirect('register')
    
    if request.method == 'POST':
        firstname = request.POST.get('firstname')
        surname = request.POST.get('surname')
        gender = request.POST.get('gender')
        dob = request.POST.get('dob')
        phone = request.POST.get('phone')
        phone_country_code = request.POST.get('phone_country_code', '+84')
        
        email = request.session.get('email')
        password = request.session.get('password')

        user = None
        if not User.objects.filter(email=email).exists():
            user = User.objects.create_user(username=email, password=password, email=email)
            user.first_name = firstname 
            user.last_name = surname  
            user.save()
        else:
            user = User.objects.get(email=email)
            user.first_name = firstname 
            user.last_name = surname  
            user.set_password(password) 
            user.save() 

        if not Patient.objects.filter(email=email, is_verified=True).exists():  
            patient = Patient(user=user, firstname=firstname, surname=surname, gender=gender, dob=dob, email=email, phone=phone, phone_country_code=phone_country_code, is_verified=True)
            patient.save()
        else:
            patient = Patient.objects.get(email=email, is_verified=True)    
            patient.firstname = firstname
            patient.surname = surname
            patient.gender = gender
            patient.dob = dob
            patient.phone = phone
            patient.phone_country_code = phone_country_code
            patient.save()  

        if not InsuranceInfo.objects.filter(user=user).exists():
            InsuranceInfo.objects.create(
                user=user,
                coverage="No coverage",
                insurance_company="",
                policy_number=""
            )

        user = authenticate(request, username=email, password=password)   
        
        login(request, user)

        next_url = request.session.get('next_url', '')

        return redirect(next_url if next_url else "home")
       

        # messages.success(request, _('Account registration successful'), extra_tags='accSuccess')

        # return redirect('login')
    return render(request, 'account/signup2.html')         

@csrf_exempt
def home(request):
    utm_source = request.GET.get('utm_source')
    if utm_source:
        request.session['utm_source'] = utm_source
    request.session.pop('filter_form_data', None)
    request.session.pop('firstname', None)
    request.session.pop('surname', None)
    request.session.pop('gender', None)
    request.session.pop('dob', None)
    request.session.pop('email', None)
    request.session.pop('phone', None)
    request.session.pop('selected_hospital_id', None)
    request.session.pop('firstdate', None)
    request.session.pop('firstdatefrom', None)
    request.session.pop('firstdateto', None)
    request.session.pop('seconddate', None)
    request.session.pop('seconddatefrom', None)
    request.session.pop('seconddateto', None)
    request.session.pop('symptom', None)
    request.session.pop('duration', None)
    request.session.pop('moreinfo', None)
    request.session.pop('coverage', None)
    request.session.pop('insuranceCompany', None)
    request.session.pop('policyNumber', None)
    request.session.pop('next_url', None)
    request.session['completed'] = False
    request.session['odds_session'] = None
    request.session.pop('conclusion_details', None)
    request.session.pop('rejected_booking_id', None)
    request.session.modified = True

    image_url = request.build_absolute_uri(settings.STATIC_URL + "home/card.png")

    show_resume_button = False
    if request.user.is_authenticated:
        firstname = request.user.patient.firstname
        surname = request.user.patient.surname

        last_session_hospital_booking = HospitalBooking.objects.filter(user=request.user).order_by('-created_at').first()
        if last_session_hospital_booking:
            time_since_created = timezone.now() - last_session_hospital_booking.created_at
            if (last_session_hospital_booking.status == 'rejected' or last_session_hospital_booking.status == 'canceled') and time_since_created < timedelta(days=2):
                show_resume_button = True
            else:
                show_resume_button = False
        else:
            show_resume_button = False

    else:
        firstname = None
        surname = None
        
    current_time = datetime.now()
    hour = current_time.hour

    if 6 <= hour < 12:
        greeting = _("Good Morning")
    elif 12 <= hour < 18:
        greeting = _("Good Afternoon")
    else:
        greeting = _("Good Evening")
    
    if request.user.is_authenticated:
        last_session_symptom_checker = SymptomCheckSession.objects.filter(user=request.user).order_by('-created_at')
        for last in last_session_symptom_checker:
            last.conclusion_text = _(last.conclusion_text)
        
        last_session_hospital_booking = HospitalBooking.objects.filter(user=request.user).order_by('-created_at')
    else:
        last_session_symptom_checker = []
        last_session_hospital_booking = []
    hospitals_by_country = Hospital.objects.values('country').annotate(count=Count('id')).order_by('country')
    insurances = Insurance.objects.all()
    translated_insurances = [(insurance, _(insurance.name)) for insurance in insurances]
    countries = []
    for entry in hospitals_by_country:
        country_code = entry['country']
        count = entry['count']
        if country_code == 'LA':
            country_name = _("Laos")
        elif country_code == 'KR':
            country_name = _("Korea")
        elif country_code == 'TW':
            country_name = _("Taiwan")
        else:
            country_name = _(pycountry.countries.get(alpha_2=country_code).name) if country_code else 'Unknown'
        countries.append((country_code, country_name, count))

    

    combined_sessions = sorted(
        chain(last_session_symptom_checker, last_session_hospital_booking),
        key=attrgetter('created_at'),
        reverse=True
    )
    
    current_language = get_language()
    context = {
        'firstname': firstname,
        'surname': surname,
        'greeting': greeting,
        'combined_sessions': combined_sessions,
        'show_resume_button': show_resume_button,
        'insurances': translated_insurances,
        'countries': countries,
        'current_language': current_language,
        'image_url': image_url,
        'MEDIA_URL': settings.MEDIA_URL,
    }
    return render(request, 'home/index.html', context)

@login_required
@csrf_exempt
def myData(request):
    firstname = request.user.patient.firstname
    surname = request.user.patient.surname
    email = request.user.patient.email
    phone = request.user.patient.phone
    height = request.user.patient.height
    weight = request.user.patient.weight
    is_patient = request.user.patient.is_patient
    height_unit = request.user.patient.height_unit
    weight_unit = request.user.patient.weight_unit

    saved_hospitals_count = FavouriteHospital.objects.filter(user=request.user).count()
    insurance = InsuranceInfo.objects.filter(user=request.user)
    for ins in insurance:
        ins.coverage = _(ins.coverage)
    booked_hosipitals_count = HospitalBooking.objects.filter(user=request.user).count()

    context = {
        'firstname': firstname,
        'surname': surname,
        'email': email,
        'phone': phone,
        'saved_hospitals_count': saved_hospitals_count,
        'insurance': insurance,
        'booked_hosipitals_count': booked_hosipitals_count,
        'height': height,
        'weight': weight,
        'is_patient': is_patient,
        'height_unit': height_unit,
        'weight_unit': weight_unit,
        'current_language': get_language(),
        'MEDIA_URL': settings.MEDIA_URL,
    }

    return render(request, 'account/mydata.html', context)

@login_required
@csrf_exempt
def accountPage(request):
    firstname = request.user.patient.firstname
    surname = request.user.patient.surname
    is_patient = request.user.patient.is_patient

    context = {
        'firstname': firstname,
        'surname': surname,
        'is_patient': is_patient,
    }

    return render(request, 'account/account.html', context)

@login_required
@csrf_exempt
def personalPage(request):
    request.session.pop('new_email', None)
    firstname = request.user.patient.firstname
    surname = request.user.patient.surname
    gender = request.user.patient.gender
    dob = request.user.patient.dob
    email = request.user.patient.email
    nationality = request.user.patient.nationality
    language = request.user.patient.language
    phone = request.user.patient.phone
    phone = phone.lstrip('0') 
    phone_country_code = request.user.patient.phone_country_code

    if nationality is None:
        nationality_display = None
    else:
        nationality_display = _(nationality)

    context = {
        'firstname': firstname,
        'surname': surname,
        'gender': gender,
        'dob': dob,
        'email': email,
        'nationality': nationality_display, 
        'language': language,
        'phone': phone,
        'phone_country_code': phone_country_code,
    }

    return render(request, 'account/personal.html', context)


@login_required
@csrf_exempt
def medicalInfoPage(request):
    firstname = request.user.patient.firstname
    surname = request.user.patient.surname
    gender = request.user.patient.gender
    dob = request.user.patient.dob
    height = request.user.patient.height
    weight = request.user.patient.weight
    height_unit = request.user.patient.height_unit
    weight_unit = request.user.patient.weight_unit

    context = {
        'firstname': firstname,
        'surname': surname,
        'gender': gender,
        'dob': dob,
        'height': height,
        'weight': weight,
        'height_unit': height_unit,
        'weight_unit': weight_unit,
    }

    return render(request, 'account/medicalInfo.html', context)

@login_required
@csrf_exempt
def setting(request):
    language_code_map = {
        'jp': 'ja',
        'vn': 'vi', 
    }

    current_language_code = get_language()
    standard_language_code = language_code_map.get(current_language_code, current_language_code)
    current_language_info = get_language_info(standard_language_code)
    
    context = {
        'current_language': _(current_language_info['name']),
    }

    return render(request, 'account/setting.html', context)

@login_required
@csrf_exempt
def passwordsecurityPage(request):
    context = {}

    return render(request, 'account/password&securityPage.html', context)

@login_required
@csrf_exempt
def changePassword(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user) 
            return redirect('passwordsecurityPage')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'account/changePassword.html', {'form': form})

@login_required
@csrf_exempt
def update_insurance(request):
    page = "insurance"
    insurance_info = InsuranceInfo.objects.get(user=request.user)
    if request.method == 'POST':
        coverage = request.POST.get('coverage')
        policy_number = request.POST.get('policy_number')
        insurance_company = request.POST.get('insurance_company')
        insurance_info.coverage = coverage
        if coverage == "No coverage":
            insurance_info.policy_number = ""
            insurance_info.insurance_company = ""
        elif not coverage == "No coverage" and not coverage == "Others":
            insurance_info.insurance_company = ""
            insurance_info.policy_number = policy_number
        else:
            insurance_info.policy_number = policy_number
            insurance_info.insurance_company = insurance_company
        insurance_info.save()
        return redirect('insurance')
    
    context = {
        'current_coverage': _(insurance_info.coverage),
        'current_coverage1': insurance_info.coverage,
        'current_policy_number': _(insurance_info.policy_number) if insurance_info.policy_number else '',
        'current_insurance_company': _(insurance_info.insurance_company) if insurance_info.insurance_company else '',
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_fullname(request):
    page = "fullname"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_firstname = request.POST.get('firstname')
        new_surname = request.POST.get('surname')
        patient_profile.firstname = new_firstname
        patient_profile.surname = new_surname
        patient_profile.save()
        return redirect('personal')
    
    context = {
        'current_firstname': patient_profile.firstname,
        'current_surname': patient_profile.surname,
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_gender(request):
    page = "gender"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_gender = request.POST.get('gender')
        patient_profile.gender = new_gender
        patient_profile.save()
        return redirect('personal')
    
    context = {
        'current_gender': patient_profile.gender,
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_dob(request):
    page = "dob"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_dob = request.POST.get('dob')
        patient_profile.dob = new_dob
        patient_profile.save()
        return redirect('personal')
    
    context = {
        'current_dob': patient_profile.dob.strftime('%Y-%m-%d'), 
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_email(request):
    page = "email"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_email = request.POST.get('email')
        if User.objects.filter(username=new_email).exists():
            messages.error(request, 'Email already exists', extra_tags='emailUpdateExist')
            return redirect('update_email')
        else:
            request.session['new_email'] = new_email
            return redirect('verifyUpdateEmail')
    
    context = {
        'current_email': patient_profile.email,
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@csrf_exempt
def verifyUpdateEmail(request):
    if not request.session.get('new_email', ''):
        return redirect('update_email')
    
    verification_code = generate_verification_code_register()
    request.session['verification_code'] = verification_code 
    new_email = request.session.get('new_email', '')

    send_mail(
        _('Your Verification Code'),
        f'{_("Your verification code is")}: {verification_code}',
        'Vitabi <vitabi.info@gmail.com>',
        [new_email],
        fail_silently=False,
    )
    return render(request, 'account/signup1.html')

@login_required
@csrf_exempt
def update_nationality(request):
    page = "nationality"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_nationality = request.POST.get('nationality')
        patient_profile.nationality = new_nationality
        patient_profile.save()
        return redirect('personal')
    
    nationality = patient_profile.nationality
    
    if nationality is None:
        nationality_display = None
    else:
        nationality_display = _(nationality)
    
    context = {
        'current_nationality': nationality_display, 
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_language(request):
    page = "language"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_language = request.POST.get('language')
        patient_profile.language = new_language
        patient_profile.save()
        return redirect('personal')
    
    context = {
        'current_language': patient_profile.language, 
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_phone(request):
    page = "phone"
    patient_profile = request.user.patient
    if request.method == 'POST':
        new_phone = request.POST.get('phone')
        phone_country_code = request.POST.get('phone_country_code', '+84')
        patient_profile.phone = new_phone
        patient_profile.phone_country_code = phone_country_code
        patient_profile.save()
        return redirect('personal')
    
    context = {
        'current_phone': patient_profile.phone, 
        'page': page,
        'phone_country_code': patient_profile.phone_country_code 
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_height(request):
    page = "height"
    patient_profile = request.user.patient

    if request.method == 'POST':
        new_height = request.POST.get('height')
        height_unit = request.POST.get('height_unit')
        
        try:
            new_height = float(new_height)
            
            if new_height < 0:
                return redirect('medicalInfo')
            
            patient_profile.height = new_height
            patient_profile.height_unit = height_unit  
            patient_profile.save()
            
        
            return redirect('medicalInfo')
        except (ValueError, TypeError):
            return redirect('medicalInfo')
    
    context = {
        'current_height': patient_profile.height,
        'height_unit': patient_profile.height_unit,
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@login_required
@csrf_exempt
def update_weight(request):
    page = "weight"
    patient_profile = request.user.patient

    if request.method == 'POST':
        new_weight = request.POST.get('weight')
        weight_unit = request.POST.get('weight_unit')
        
        try:
            new_weight = float(new_weight)
            if new_weight < 0:
                return redirect('medicalInfo')
            
            patient_profile.weight = new_weight
            patient_profile.weight_unit = weight_unit  
            patient_profile.save()
            
            return redirect('medicalInfo')
        except (ValueError, TypeError):
            return redirect('medicalInfo')
    
    context = {
        'current_weight': patient_profile.weight,
        'page': page,
    }
    return render(request, 'account/update_personal.html', context)

@csrf_exempt
@csrf_exempt
def change_language(request):
    page = "language"
    
    if request.method == 'POST':
        language = request.POST.get('language', 'en')
        next_page = request.POST.get('next','/')
        print(next_page)
        translation.activate(language) 
        if next_page == "setting":
            response = redirect('setting')
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
            return response
        else:
            response = redirect(next_page)
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, language)
            return response
        
    current_language = translation.get_language()
        
    context = {
        'page': page,
        'current_language': current_language,
    }
    
    return render(request, 'account/update_setting.html', context)

@csrf_exempt
def update_hospital_rating(hospital):
    new_rating = fetch_hospital_rating(hospital.name)
    if new_rating is not None:
        hospital.rating = new_rating
        hospital.updated_at = now()
        hospital.save()

@csrf_exempt
def findHospital(request):
    request.session.pop('selected_hospital_id', None)
    if request.user.is_authenticated:
        favourite_hospitals_ids = request.user.favourite_hospitals.values_list('hospital', flat=True)
    else:
        favourite_hospitals_ids = []

    resume = request.GET.get('resume', False)
    if resume:
        last_rejected_booking = HospitalBooking.objects.filter(
            Q(user=request.user) & (Q(status='rejected') | Q(status='canceled'))
        ).order_by('-created_at').first()

        if last_rejected_booking:
            request.session['rejected_booking_id'] = last_rejected_booking.id
    else:
        request.session.pop('rejected_booking_id', None)
        

    hospitals = Hospital.objects.annotate(
        is_favourite=Case(
            When(id__in=list(favourite_hospitals_ids), then=Value(True)),
            default=Value(False),
            output_field=BooleanField()
        )
    ).order_by('-is_favourite', 'name')

    if request.method == 'GET':
        request.session['filter_form_data'] = request.GET.dict()

    filter_form_data = request.session.get('filter_form_data', {})
    search_query = filter_form_data.get('q')
    country_query = filter_form_data.get('country')
    current_time_filter = filter_form_data.get('current_time_filter')
    insurance_filter = filter_form_data.get('insurance')
    language_filter = filter_form_data.get('language')
    distance_filter = filter_form_data.get('distance')
    custom_distance = filter_form_data.get('custom_distance')
    allday_filter = filter_form_data.get('allday', False)
    custom_time_from = filter_form_data.get('time_from', None)
    custom_time_to = filter_form_data.get('time_to', None)
    date_filter = filter_form_data.get('date_filter', None)
    if date_filter:
        date_filter = datetime.strptime(date_filter, '%Y-%m-%d').date()

    hospital_ids = []
    if custom_distance:
        try:
            custom_distance = float(custom_distance)
            for info in DistanceInfo.objects.all():
                distance_value = float(info.distance_text.replace(' km', '').replace(',', ''))
                if distance_value <= custom_distance:
                    hospital_ids.append(info.hospital_id)
        except ValueError:
            custom_distance = None 

        hospitals = Hospital.objects.filter(id__in=hospital_ids)

    if distance_filter:
        max_distance = float(filter_form_data['distance'])
        hospital_ids = []
        for info in DistanceInfo.objects.all():
            try:
                distance_value = info.distance_text.replace(' km', '').replace(',', '')
                if float(distance_value) <= max_distance:
                    hospital_ids.append(info.hospital_id)
            except ValueError:
                continue  

        hospitals = hospitals.filter(id__in=hospital_ids)

    if allday_filter == 'allday':
        hospitals = hospitals.filter(
            working_hours__open_time=time(0, 0),
            working_hours__close_time=time(23, 59)
        ).distinct()

    if date_filter and custom_time_from and custom_time_to:
        custom_time_from = datetime.strptime(custom_time_from, '%H:%M').time()
        custom_time_to = datetime.strptime(custom_time_to, '%H:%M').time()
        day_of_week = date_filter.strftime('%A')

        hospitals = hospitals.filter(
            working_hours__day_of_week__iexact=day_of_week,
            working_hours__open_time__lte=custom_time_from,
            working_hours__close_time__gte=custom_time_to
        ).distinct()

    if search_query:
        translator = Translator()
        translated_query = translator.translate(search_query, src='auto', dest='en').text
        translated_query = unidecode(translated_query)
        
        hospitals = hospitals.filter(
            Q(name__icontains=translated_query) | Q(country__icontains=translated_query) | Q(address__icontains=translated_query)
        )

    if country_query:
        hospitals = hospitals.filter(country__iexact=country_query)

    if insurance_filter:
        hospitals = hospitals.filter(supported_insurance__name__icontains=insurance_filter)

    if 'affiliated_with_insurers' in filter_form_data:
        hospitals = hospitals.annotate(insurance_count=Count('supported_insurance')).filter(insurance_count__gt=0)

    if 'japanese_speaking_staff' in filter_form_data:
        hospitals = hospitals.filter(supported_languages__name__icontains="Japanese")
        
    if 'english_speaking_staff' in filter_form_data:
        hospitals = hospitals.filter(supported_languages__name__icontains="English")

    if language_filter == "Japanese":
        hospitals = hospitals.filter(supported_languages__name__icontains="Japanese")

    final_hospitals = list(hospitals)  

    if current_time_filter == "true":
        final_hospitals = [hospital for hospital in final_hospitals if hospital.is_open_now()]

    for hospital in hospitals:
        if hospital.latitude is None or hospital.longitude is None:
            lat, lon = fetch_coordinates(hospital.address)
            if lat and lon:
                hospital.latitude = lat
                hospital.longitude = lon
                hospital.save()

    open_status = {hospital.id: hospital.is_open_now() for hospital in hospitals}

    hospital_working_hours = {}
    today = datetime.now().strftime('%A')
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for hospital in hospitals:
        working_hours = list(hospital.working_hours.all())
        working_hours_sorted = sorted(
            working_hours,
            key=lambda wh: days_order.index(wh.day_of_week)
        )
        working_hours_dict = defaultdict(list)
        for hours in working_hours_sorted:
            time_range = f"{hours.open_time.strftime('%H:%M')} - {hours.close_time.strftime('%H:%M')}"
            working_hours_dict[hours.day_of_week].append(time_range)

        formatted_working_hours = []
        for day in days_order:
            if working_hours_dict.get(day):
                times = working_hours_dict[day]
                formatted_working_hours.append({
                    'day': _(day),
                    'time': ' / '.join(times)
                })
            else:
                formatted_working_hours.append({'day': _(day), 'time': _('Closed')})

        hospital_working_hours[hospital.id] = formatted_working_hours

    today_index = days_order.index(today)
    for hospital_id, hours in hospital_working_hours.items():
        hospital_working_hours[hospital_id] = hours[today_index:] + hours[:today_index]

    context = {
        'hospitals': final_hospitals,
        'favourite_hospitals_ids': favourite_hospitals_ids,
        'open_status': open_status,
        'hospital_working_hours': hospital_working_hours,
        'filter_form_data': filter_form_data, 
        'current_language': get_language(),
    }

    return render(request, 'home/findHospital.html', context)

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

@csrf_exempt
def save_distance_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        hospital_id = data.get('hospital_id')
        distance_text = data.get('distance_text')

        logger.error(f"Received data: hospital_id={hospital_id}, distance_text={distance_text}")

        if hospital_id and distance_text:
            hospital = Hospital.objects.get(id=hospital_id)
            distance_info, created = DistanceInfo.objects.get_or_create(hospital=hospital)
            distance_info.distance_text = distance_text
            distance_info.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'success': False, 'error': 'Missing data'}, status=400)
    else:
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

def fetch_coordinates(address):
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    
    logger.info(f"Using API Key: {settings.GOOGLE_MAPS_API_KEY}")
    
    response = requests.get(base_url, params=params)
    if response.status_code == 200:
        results = response.json().get('results')
        if results:
            location = results[0].get('geometry').get('location')
            return location['lat'], location['lng']
    else:
        logger.error(f"Geocoding API error: {response.json().get('status')} for address: {address}")
    
    return None, None

@csrf_exempt
def fetch_distance_and_duration(origin, destination):
    api_url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        'origins': origin,
        'destinations': destination,
        'key': settings.GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(api_url, params=params)
    data = response.json()

    if data['status'] == 'OK':
        element = data['rows'][0]['elements'][0]
        if element['status'] == 'OK':
            distance_text = element['distance']['text']
            duration_text = element['duration']['text']
            return distance_text, duration_text
    return None, None

@login_required
@csrf_exempt
def add_to_favourites(request, hospital_id):
    hospital = get_object_or_404(Hospital, pk=hospital_id)
    FavouriteHospital.objects.get_or_create(user=request.user, hospital=hospital)
    page = request.GET.get('page', 'findHospital')
    if page == "findHospital":
        return redirect('findHospital')
    if page == "hospitalInfo":
        return redirect('hospitalInfo', pk=hospital_id)
        
@login_required
@csrf_exempt
def remove_from_favourites(request, hospital_id):
    hospital = get_object_or_404(Hospital, pk=hospital_id)
    FavouriteHospital.objects.filter(user=request.user, hospital=hospital).delete()
    page = request.GET.get('page', 'findHospital')
    if page == "findHospital":
        return redirect('findHospital')
    if page == "hospitalInfo":
        return redirect('hospitalInfo', pk=hospital_id)
    
def translate_text(text, target_language):
    api_key = settings.GOOGLE_MAPS_API_KEY
    url = f"https://translation.googleapis.com/language/translate/v2"
    
    params = {
        'q': text,
        'target': target_language,
        'key': api_key
    }
    response = requests.post(url, data=params)
    response_data = response.json()

    if 'data' in response_data and 'translations' in response_data['data']:
        return response_data['data']['translations'][0]['translatedText']
    else:
        print(f"Error in translation: {response_data.get('error', {}).get('message', 'Unknown error')}")
        return text  # Trả về văn bản gốc nếu có lỗi

import re
import mimetypes
import requests
from urllib.parse import urlparse
from django.core.files.base import ContentFile 

import hashlib

def get_image_hash(image_content):
    return hashlib.md5(image_content).hexdigest()

def is_valid_url(url):
    parsed = urlparse(url)
    return all([parsed.scheme, parsed.netloc])

def update_hospital_from_api(hospital):
    if not hospital.placeId:
        search_query_name_address = f"{hospital.name}, {hospital.address}"
        search_query_name = hospital.name
        
        url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={search_query_name_address}&inputtype=textquery&fields=place_id&locationbias=point:{hospital.latitude},{hospital.longitude}&key={settings.GOOGLE_MAPS_API_KEY}"
        response = requests.get(url)
        data = response.json()

        if data['status'] == 'OK' and 'candidates' in data and len(data['candidates']) > 0:
            hospital.placeId = data['candidates'][0]['place_id']
            hospital.save()
        else:
            url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={search_query_name}&inputtype=textquery&fields=place_id&locationbias=point:{hospital.latitude},{hospital.longitude}&key={settings.GOOGLE_MAPS_API_KEY}"
            response = requests.get(url)
            data = response.json()

            if data['status'] == 'OK' and 'candidates' in data and len(data['candidates']) > 0:
                hospital.placeId = data['candidates'][0]['place_id']
                hospital.save()
            else:
                print(f"Error fetching place ID: {data.get('error_message', 'Unknown error')}")
                return

    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={hospital.placeId}&fields=name,rating,user_ratings_total,reviews,photos,formatted_address&key={settings.GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    data = response.json()

    if 'result' in data:
        place_details = data['result']
        hospital.name = place_details.get('name', hospital.name)
        hospital.address = place_details.get('formatted_address', hospital.address)
        hospital.rating = place_details.get('rating', hospital.rating) * 2 if place_details.get('rating') else hospital.rating
        hospital.user_ratings_total = place_details.get('user_ratings_total', hospital.user_ratings_total)
        hospital.last_api_update = timezone.now()
        hospital.save()

        existing_hashes = set(hospital.images.values_list('unique_url', flat=True)) 
        if 'photos' in place_details:
            for photo_data in place_details['photos']:
                photo_reference = photo_data.get('photo_reference')
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=400&photoreference={photo_reference}&key={settings.GOOGLE_MAPS_API_KEY}"
                
                if is_valid_url(photo_url):
                    image_response = requests.get(photo_url)
                    if image_response.status_code == 200:
                        image_hash = get_image_hash(image_response.content)  
                        if image_hash not in existing_hashes:
                            mime_type = image_response.headers.get('Content-Type')
                            extension = mimetypes.guess_extension(mime_type)
                            if extension:
                                HospitalImage.objects.create(
                                    hospital=hospital,
                                    photo=ContentFile(image_response.content, name=f"{photo_reference}{extension}"),
                                    original_url=photo_url,
                                    unique_url=image_hash,
                                )
                                existing_hashes.add(image_hash) 
        else:
            search_query_name_address_photo = f"{hospital.name}, {hospital.address}"
            custom_search_url_address = f"https://www.googleapis.com/customsearch/v1?q={search_query_name_address_photo}&cx={settings.GOOGLE_CUSTOM_SEARCH_CX}&searchType=image&key={settings.GOOGLE_CUSTOM_SEARCH_API_KEY}"
            custom_response_address = requests.get(custom_search_url_address)
            custom_data_address = custom_response_address.json()

            if 'items' in custom_data_address:
                custom_data = custom_data_address
            else:
                search_query_name_photo = hospital.name
                custom_search_url_name = f"https://www.googleapis.com/customsearch/v1?q={search_query_name_photo}&cx={settings.GOOGLE_CUSTOM_SEARCH_CX}&searchType=image&key={settings.GOOGLE_CUSTOM_SEARCH_API_KEY}"
                custom_response_name = requests.get(custom_search_url_name)
                custom_data = custom_response_name.json()

            if 'items' in custom_data:
                for item in custom_data['items']:
                    image_link = item.get('link')
                    
                    if not hospital.images.filter(unique_url=image_link).exists():
                        if is_valid_url(image_link):
                            image_response = requests.get(image_link)
                            if image_response.status_code == 200:
                                mime_type = image_response.headers.get('Content-Type')
                                extension = mimetypes.guess_extension(mime_type)
                                if extension:  
                                    HospitalImage.objects.create(
                                        hospital=hospital,
                                        photo=ContentFile(image_response.content, name=f"{hash(image_link)}{extension}"),
                                        original_url=image_link,
                                        unique_url=image_link
                                    )

        if 'reviews' in place_details:
            existing_reviews = Review.objects.filter(hospital=hospital).values('author_name', 'text', 'review_time', 'author_url')
            existing_reviews_set = {(review['author_name'], review['text'], review['review_time'], review['author_url']) for review in existing_reviews}

            for review_data in place_details['reviews']:
                timestamp = review_data.get('time')
                review_datetime = datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else timezone.now()
                author_name = review_data.get('author_name', '')
                text = review_data.get('text', '').strip()
                author_url = review_data.get('author_url', '')

                if (author_name, text, review_datetime, author_url) not in existing_reviews_set:
                    new_review = Review.objects.create(
                        hospital=hospital,
                        author_name=author_name,
                        text=text,
                        rating=review_data.get('rating', 0),
                        review_time=review_datetime,
                        profile_photo_url=review_data.get('profile_photo_url'),
                        author_url=author_url
                    )

                    if not TranslatedReview.objects.filter(review=new_review, language='ja').exists():
                        translated_text = translate_text(text, 'ja')
                        TranslatedReview.objects.create(
                            review=new_review,
                            language='ja',
                            translated_text=translated_text
                        )
    else:
        print(f"Error fetching place details: {data.get('error_message', 'Unknown error')}")





@csrf_exempt
def hospitalInfo(request, pk):
    request.session.pop('firstname', None)
    request.session.pop('surname', None)
    request.session.pop('gender', None)
    request.session.pop('dob', None)
    request.session.pop('email', None)
    request.session.pop('phone', None)
    request.session.pop('selected_hospital_id', None)
    request.session.pop('firstdate', None)
    request.session.pop('firstdatefrom', None)
    request.session.pop('firstdateto', None)
    request.session.pop('seconddate', None)
    request.session.pop('seconddatefrom', None)
    request.session.pop('seconddateto', None)
    request.session.pop('symptom', None)
    request.session.pop('duration', None)
    request.session.pop('moreinfo', None)
    request.session.pop('coverage', None)
    request.session.pop('insuranceCompany', None)
    request.session.pop('policyNumber', None)
    if request.user.is_authenticated:
        favourite_hospitals_ids = request.user.favourite_hospitals.values_list('hospital', flat=True)
    else:
        favourite_hospitals_ids = []
        
    hospital = Hospital.objects.get(id=pk)
    request.session['selected_hospital_id'] = hospital.id

    if not hospital.last_api_update or (timezone.now() - hospital.last_api_update > timedelta(days=14)):
        update_hospital_from_api(hospital)

    japanese_available = hospital.supported_languages.filter(name='Japanese').exists()
    english_available = hospital.supported_languages.filter(name='English').exists()

    working_hours = list(WorkingHours.objects.filter(hospital=hospital))
    today = datetime.now().strftime('%A')
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    working_hours_sorted = sorted(
        working_hours,
        key=lambda wh: days_order.index(wh.day_of_week)
    )

    working_hours_dict = defaultdict(list)
    for hours in working_hours_sorted:
        time_range = f"{hours.open_time.strftime('%H:%M')} - {hours.close_time.strftime('%H:%M')}"
        working_hours_dict[hours.day_of_week].append(time_range)

    formatted_working_hours = []
    for day in days_order:
        if working_hours_dict.get(day):
            times = working_hours_dict[day]
            formatted_working_hours.append({
                'day': _(day),
                'time': ' / '.join(times),
                'is_open': times != ['Closed']
            })

    if 'Sunday' not in working_hours_dict:
        formatted_working_hours.append({'day': _('Sunday'), 'time': _('Closed')})


    hospitals_booking_id = request.session.get('hospitals_booking_id', '')

    saved_data = request.session.get('filter_form_data', {})
    filter_query_string = urlencode(saved_data)

    reviews = []
    for review in hospital.reviews.all():
        translation = review.translations.filter(language='ja').first() if get_language() == 'jp' else None
        reviews.append({
            'author_name': review.author_name,
            'text': translation.translated_text if translation else review.text,
            'rating': review.rating,
            'time_since': review.time_since(),
            'profile_photo_url': review.profile_photo_url,
        })

    context = {
        'hospital' : hospital,
        'favourite_hospitals_ids': favourite_hospitals_ids,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'formatted_working_hours': formatted_working_hours,
        'hospitals_booking_id': hospitals_booking_id,
        'filter_query_string': filter_query_string,
        'japanese_available': japanese_available,
        'english_available': english_available,
        'current_language': get_language(),
        'reviews': reviews,
    }
    
    return render(request, 'home/hospitalInfo.html', context)

@csrf_exempt
def bookedHospitalDetail(request, pk):
    hospitalBooking = HospitalBooking.objects.get(id=pk)
    coverage = _(hospitalBooking.coverage)
    status = _(hospitalBooking.status)

    context = {
        'hospitalBooking' : hospitalBooking,
        'coverage' : coverage,
        'status' : status,
    }
    
    return render(request, 'home/bookedHospitalDetail.html', context)

# @csrf_exempt
# def diagnose(request, question_id=None):
#     if 'history' not in request.session:
#         request.session['history'] = []
    
#     if request.session.get('completed', False):
#         context = request.session.get('final_context', {})
#         return render(request, 'home/conclusion.html', context)
    
#     if question_id is None:
#         question = Question.objects.get(is_first_question=True)
#         request.session['current_odds'] = 1
#         request.session['history'] = [question.id]
#     else:
#         question = get_object_or_404(Question, id=question_id)

#     previous_question_id = None
#     if request.method == 'POST':
#         answer_id = request.POST.get('answer')
#         answer = get_object_or_404(Answer, id=answer_id)
#         current_odds = request.session.get('current_odds', 1)

#         if answer.likelihood_ratio:
#             new_odds = current_odds * answer.likelihood_ratio
#         else:
#             new_odds = current_odds

#         request.session['current_odds'] = new_odds
#         request.session['history'].append(question.id if answer.next_question else None)
#         request.session.modified = True

#         if answer.is_conclusive:
#             conclusions = answer.conclusions.all()
#             selected_conclusion = None
#             for conclusion in conclusions:
#                 if (new_odds >= 1 and conclusion.odds_condition == '>=1') or (new_odds < 1 and conclusion.odds_condition == '<1'):
#                     selected_conclusion = conclusion.text
#                     odds_conclusion = conclusion.odds_condition
#                     id_conclusion = conclusion.id
#                     break
#             conclusion_text = selected_conclusion or "No appropriate conclusion could be determined."
        
#             probability = new_odds / (1 + new_odds)
#             probability_percent = "{:.2%}".format(probability)
#             odds_percentage = float(probability_percent.replace('%', ''))
#             context = {
#                 'conclusion': _(conclusion_text),
#                 'odds_conclusion': odds_conclusion,
#                 'id_conclusion': id_conclusion,
#                 'odds': probability_percent,
#                 'odds_css': odds_percentage,
#             }
#             request.session['completed'] = True 
#             request.session['final_context'] = context
#             request.session['odds_session'] = probability_percent
#             request.session.modified = True
#             if request.user.is_authenticated:
#                 SymptomCheckSession.objects.create(
#                     user=request.user,
#                     conclusion_text=conclusion_text,
#                     odds_percentage=probability_percent,
#                     id_conclusion=id_conclusion
#                 )
#             return render(request, 'home/conclusion.html', context)
#         elif answer.next_question:
#             return redirect('diagnose', question_id=answer.next_question_id)
#     else:
#         if len(request.session['history']) > 1:
#             previous_question_id = request.session['history'][-1]
    
#     context = {
#         'question': question,
#         'previous_question_id': previous_question_id,
#     }
#     return render(request, 'home/question.html', context)

@csrf_exempt
def conclusion_detail(request, id_conclusion):
    conclusion = Conclusion.objects.get(id=id_conclusion) if id_conclusion else None
    if request.user.is_authenticated:
        conclusion_session = SymptomCheckSession.objects.filter(id_conclusion=id_conclusion).order_by('-created_at').first() if id_conclusion else None
        odds_percentage = float(conclusion_session.odds_percentage.replace('%', ''))
    else:
        odds_percentage = float(request.session['odds_session'].replace('%', ''))

    context = {
        'conclusion': conclusion,
        'odds': odds_percentage,
    }
    return render(request, 'home/conclusion_detail.html', context)

@login_required
@csrf_exempt
def history(request):
    history = SymptomCheckSession.objects.filter(user=request.user).order_by('-created_at')
    
    for his in history:
        his.conclusion_text = _(his.conclusion_text)
    
    context = {
        'histories': history
    }
    return render(request, 'home/history.html', context)

@login_required
@csrf_exempt
def saved(request):
    save = FavouriteHospital.objects.filter(user=request.user)

    open_status = {hos.hospital.id: hos.hospital.is_open_now() for hos in save}

    hospital_working_hours = {}
    today = datetime.now().strftime('%A')
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for hos in save:
        working_hours = list(hos.hospital.working_hours.all())
        working_hours_sorted = sorted(
            working_hours,
            key=lambda wh: (wh.day_of_week != today, days_order.index(wh.day_of_week))
        )
        formatted_working_hours = [
            f"{_(hours.day_of_week)}: {hours.open_time.strftime('%H:%M')} - {hours.close_time.strftime('%H:%M')}"
            for hours in working_hours_sorted
        ]

        if 'Sunday' not in [hours.day_of_week for hours in working_hours]:
            formatted_working_hours.append(_('Sunday: Closed'))

        hospital_working_hours[hos.hospital.id] = formatted_working_hours

    context = {
        'saved': save,
        'open_status': open_status,
        'hospital_working_hours': hospital_working_hours,
    }
    return render(request, 'home/saved.html', context)

import pycountry
@csrf_exempt
def filter(request):
    saved_data = request.session.get('filter_form_data', {})
    filter_query_string = urlencode(saved_data)
    hospitals_by_country = Hospital.objects.values('country').annotate(count=Count('id')).order_by('country')
    insurances = Insurance.objects.all()
    translated_insurances = [(insurance, _(insurance.name)) for insurance in insurances]

    distance_counts = {}
    distances = [1, 3, 5] 
    for distance in distances:
        hospital_ids = []
        for info in DistanceInfo.objects.all():
            try:
                distance_value = float(info.distance_text.replace(' km', '').replace(',', ''))
                if distance_value <= distance:
                    hospital_ids.append(info.hospital_id)
            except ValueError:
                continue
        distance_counts[distance] = len(set(hospital_ids)) 

    countries = []
    for entry in hospitals_by_country:
        country_code = entry['country']
        count = entry['count']
        country_name = _(pycountry.countries.get(alpha_2=country_code).name) if country_code else 'Unknown'
        countries.append((country_code, country_name, count))

    context = {
        'insurances': translated_insurances,
        'countries': countries,
        'saved_data': saved_data,
        'distance_counts': distance_counts,
        'filter_query_string': filter_query_string,
    }
    return render(request, 'home/filter.html', context)


def reset_filter(request):
    if 'filter_form_data' in request.session:
        del request.session['filter_form_data']

    return redirect('filter')

@csrf_exempt
def fetch_hospital_rating(hospital_name):
    api_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
    params = {
        'input': hospital_name + " hospital",
        'inputtype': 'textquery',
        'fields': 'rating',
        'key': settings.GOOGLE_MAPS_API_KEY,
    }
    response = requests.get(api_url, params=params)
    data = response.json()

    if data['status'] == 'OK' and data['candidates']:
        return data['candidates'][0].get('rating')
    return None

@csrf_exempt
def generate_verification_code():
    return ''.join(random.choices(string.digits, k=5))

@csrf_exempt
def book2Page(request):
    if not request.session.get('firstname', '') or not request.session.get('surname', ''):
        return redirect('findHospital')
    
    verification_code = generate_verification_code()
    request.session['verification_code'] = verification_code 
    email = request.session.get('email', '')
    
    send_mail(
        _('Your Verification Code'),
        f'{_("Your verification code is")}: {verification_code}',
        'Vitabi <vitabi.info@gmail.com>',
        [email],
        fail_silently=False,
    )

    hospital_id = request.session.get('selected_hospital_id')

    context = {
        'hospital_id' : hospital_id
    }

    return render(request, 'home/book2.html', context)


@csrf_exempt
def verify_account(request):
    if request.method == 'POST':
        entered_code = ''.join(request.POST.get('digit-{}'.format(i), '') for i in range(1, 6))
        if entered_code == request.session.get('verification_code'):
            return redirect('book3')
        else:
            messages.info(request, _('The verification code is incorrect. Please try again.'), extra_tags='invalidCode')
    return render(request, 'home/book2.html')

@csrf_exempt
def resend_verification_code(request):
    verification_code = generate_verification_code()
    request.session['verification_code'] = verification_code
    email = request.session.get('email', '')
    
    send_mail(
        _('Your Verification Code'),
        f'{_("Your new verification code is")}: {verification_code}',
        'Vitabi <vitabi.info@gmail.com>',
        [email],
        fail_silently=False,
    )
    
    messages.info(request, _('A new verification code has been sent to your email.'), extra_tags='resetCode')
    return render(request, 'home/book2.html')



    