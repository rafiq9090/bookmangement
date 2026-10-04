"""SMS backend function compatible with TRANSACTION_SMS_BACKEND."""
from django.conf import settings
import requests


def send_twilio_sms(phone, text):
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        raise ValueError('Twilio credentials and sender number are required.')
    response = requests.post(
        f'https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json',
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        data={'To': phone, 'From': settings.TWILIO_FROM_NUMBER, 'Body': text}, timeout=10)
    response.raise_for_status()
