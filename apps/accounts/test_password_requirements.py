from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.test import SimpleTestCase


class PasswordRequirementTests(SimpleTestCase):
    def test_missing_types_and_short_password_rejected(self):
        for value in ['lowercase123!', 'UPPERCASE123!', 'LettersOnly!', 'Letters1234', 'Aa1!']:
            with self.subTest(password=value), self.assertRaises(ValidationError):
                validate_password(value)

    def test_password_meeting_all_requirements(self):
        validate_password('Violet7392!Book')
