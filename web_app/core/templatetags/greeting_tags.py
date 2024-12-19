from django import template
from datetime import datetime

register = template.Library()

@register.simple_tag
def time_based_greeting():
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"
