from django import template
from datetime import datetime

register = template.Library()

@register.filter
def unix_to_datetime(value):
    try:
        return datetime.fromtimestamp(int(value))
    except:
        return ''
