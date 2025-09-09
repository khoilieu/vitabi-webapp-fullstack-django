# custom_filters.py
from django import template
from datetime import datetime
from django_countries import countries
import re

register = template.Library()

@register.filter
def time_to_string(value):
    return value.strftime('%H:%M:%S')

@register.filter
def to_float(value):
    try:
        return float(value.replace('%', ''))
    except ValueError:
        return 0
    
@register.filter(name='hospital_id')
def hospital_id(value, arg):
    return value.get(arg)

@register.filter
def get_distance_value(distance_infos, hospital_id):
    return distance_infos.get(hospital_id, {}).get('distance_text', '')

@register.filter
def model_name(obj):
    return obj.__class__.__name__

@register.filter
def get_value(open_status, hospital_id):
    return open_status.get(hospital_id, False)

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='first_phone')
def first_phone(value):
    phone_numbers = value.split(',')
    return phone_numbers[0].strip() if phone_numbers else ''

@register.filter(name='country_name')
def country_name(code):
    return countries.name(code)
