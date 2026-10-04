from django.http import JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def cookie_preferences(request):
    choice = request.POST.get('personalization')
    if choice not in ('yes', 'no'):
        return JsonResponse({'error': 'Choose a cookie preference.'}, status=400)
    if choice == 'no':
        request.session.pop('reading_interests', None)
    response = JsonResponse({'ok': True})
    response.set_signed_cookie('cookie_preferences', choice, salt='cookie-preferences',
        max_age=365 * 86400, httponly=True, secure=request.is_secure(), samesite='Lax')
    return response
