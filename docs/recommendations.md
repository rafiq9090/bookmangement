# Book recommendations

Content-based metadata ranking: 70% interest, 20% proximity, 10% freshness.
Interest uses genre (65%), author (25%) and language (10%). Searches teach
from at most 12 matching books; book views have twice the weight. Consecutive
refreshes of the same event do not count again. Genres allow recommendations
across authors without assuming that all books by one author have one genre.

Guest and signed-in preferences live in the current browser session, capped at
30 entries per feature and expiring after 30 days of inactivity. They are not
shared across devices. Interest learning runs in the background without Home controls.
Coordinates are stored rounded to two decimal places and only supplied through
explicit location controls. Search with a remembered location defaults to
nearest matching books; explicit sorting and filters still take precedence.

Home ranks up to 500 available candidate listings, prioritizing known genres
and authors before recent listings. This is a bounded first implementation;
large catalogs should move candidate retrieval and ranking into indexed jobs.
Recommendations rely on accurate author/category metadata. Description-based
TF-IDF and collaborative filtering are not part of this first version.
