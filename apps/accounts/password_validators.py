import re
from django.core.exceptions import ValidationError


class StrongPasswordValidator:
    def validate(self, password, user=None):
        requirements = [
            (r'[A-Z]', 'Include an uppercase letter (A–Z).'),
            (r'[a-z]', 'Include a lowercase letter (a–z).'),
            (r'[0-9]', 'Include a number (0–9).'),
            (r'[^A-Za-z0-9\s]', 'Include a symbol, such as !, @, or #.'),
        ]
        errors = [message for pattern, message in requirements if not re.search(pattern, password)]
        if errors:
            raise ValidationError(errors, code='password_missing_character_types')

    def get_help_text(self):
        return 'Include an uppercase letter, a lowercase letter, a number, and a symbol.'
