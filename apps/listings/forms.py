"""Public location input. Coordinates are deliberately rounded to area scale."""
from decimal import Decimal
from django import forms

class ListingLocationForm(forms.Form):
    district = forms.CharField(max_length=100)
    area = forms.CharField(max_length=100)
    latitude = forms.DecimalField(required=False, min_value=-90, max_value=90, max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(required=False, min_value=-180, max_value=180, max_digits=9, decimal_places=6)
    is_collectible = forms.BooleanField(required=False)

    def clean(self):
        data = super().clean()
        lat, lon = data.get('latitude'), data.get('longitude')
        if (lat is None) != (lon is None):
            raise forms.ValidationError('Provide both coordinates or neither.')
        # Public marker is approximate; exact pickup place is private.
        for field in ('latitude', 'longitude'):
            if data.get(field) is not None:
                data[field] = data[field].quantize(Decimal('.01'))
        return data


class ListingPhotoForm(forms.Form):
    photo = forms.ImageField()
    def clean_photo(self):
        photo = self.cleaned_data["photo"]
        if photo.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Each photo must be at most 10 MB.")
        return photo


class ListingDetailsForm(forms.Form):
    title = forms.CharField(max_length=255, required=False)
    author = forms.CharField(max_length=200, required=False)
    original_mrp = forms.DecimalField(max_digits=8, decimal_places=2, min_value=0, required=False)
    edition_year = forms.IntegerField(min_value=1, max_value=9999, required=False)
