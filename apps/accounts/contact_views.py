from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import ContactMessage
from .submission_limits import limit_submission


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "w-full border border-gray-200 rounded-xl px-4 py-3 text-sm"


@require_http_methods(["GET", "POST"])
def contact(request):
    if request.method == 'POST':
        blocked = limit_submission(request, 'contact')
        if blocked is not None:
            return blocked
    initial = {}
    if request.user.is_authenticated:
        initial = {"name": request.user.get_full_name(), "email": request.user.email}
    form = ContactForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        now = timezone.now().timestamp()
        if now - request.session.get("last_contact_submission", 0) < 60:
            form.add_error(None, "Please wait one minute before sending another message.")
        else:
            form.save()
            request.session["last_contact_submission"] = now
            messages.success(request, "Your message has been sent to our support team.")
            return redirect("contact")
    return render(request, "pages/contact.html", {"form": form})
