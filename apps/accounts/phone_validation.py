import re
from django.core.exceptions import ValidationError


def normalize_bd_mobile(value):
    value = re.sub(r'[\s()-]', '', (value or '').strip())
    if not value:
        return ''
    if value.startswith('+880'):
        value = '0' + value[4:]
    elif value.startswith('880'):
        value = '0' + value[3:]
    if not re.fullmatch(r'01[3-9][0-9]{8}', value):
        raise ValidationError('Use a valid Bangladeshi mobile number, such as 01712345678.')
    return '+880' + value[1:]
