"""Evidence is never served by MEDIA_URL; access requires an authorized view."""
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

@deconstructible
class PrivateEvidenceStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=settings.PRIVATE_UPLOAD_ROOT)
    def url(self, name):
        raise ValueError('Private evidence has no public URL.')
