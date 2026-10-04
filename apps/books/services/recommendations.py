"""Bounded, session-based metadata recommendations for guests and members."""
import math
import time
from django.utils import timezone
from .osm_location import haversine_km

KEY = "reading_interests"


def profile(request):
    if request.get_signed_cookie('cookie_preferences', default='', salt='cookie-preferences', max_age=365 * 86400) != 'yes':
        return {}
    value = request.session.get(KEY, {})
    return value if value.get("updated", 0) > time.time() - 30 * 86400 else {}


def learn(request, books, event, weight=1):
    if request.get_signed_cookie('cookie_preferences', default='', salt='cookie-preferences', max_age=365 * 86400) != 'yes':
        return
    value = profile(request)
    if value.get("last_event") == event:
        return
    books = list(books)[:12]
    if not books:
        return
    for kind in ("genres", "authors", "languages"):
        scores = value.setdefault(kind, {})
        tokens = set()
        for book in books:
            if kind == "genres": tokens.update(str(cat.pk) for cat in book.categories.all())
            elif kind == "authors": tokens.update(str(author.pk) for author in book.authors.all())
            else: tokens.add(book.language.lower())
        for token in tokens:
            scores[token] = min(20, scores.get(token, 0) + weight / max(1, len(tokens)))
        value[kind] = dict(sorted(scores.items(), key=lambda item: item[1], reverse=True)[:30])
    value.update(last_event=event, updated=time.time())
    request.session[KEY] = value


def coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (ValueError, TypeError):
        pass
    return None


def location(request):
    coords = request.session.get("recommendation_location", [])
    return coordinates(*coords) if len(coords) == 2 else None


def rank(listings, interests, coords=None):
    def match(kind, tokens):
        weights = interests.get(kind, {})
        maximum = max(weights.values(), default=0)
        return max((weights.get(str(token), 0) / maximum for token in tokens), default=0) if maximum else 0
    for listing in listings:
        book = listing.book
        interest = (.65 * match("genres", [c.pk for c in book.categories.all()]) +
                    .25 * match("authors", [a.pk for a in book.authors.all()]) +
                    .10 * match("languages", [book.language.lower()]))
        listing.distance_km = None
        proximity = 0
        if coords and listing.latitude is not None and listing.longitude is not None:
            listing.distance_km = haversine_km(*coords, float(listing.latitude), float(listing.longitude))
            proximity = 1 / (1 + listing.distance_km / 10)
        age = max(0, (timezone.now() - listing.created_at).total_seconds() / 86400)
        freshness = 1 / (1 + age / 30)
        listing.recommendation_score = .7 * interest + .2 * proximity + .1 * freshness
    return sorted(listings, key=lambda item: (item.recommendation_score, item.pk), reverse=True)
