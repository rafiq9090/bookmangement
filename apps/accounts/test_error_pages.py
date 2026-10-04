from django.test import TestCase, override_settings


class ErrorPageTests(TestCase):
    def test_preview_returns_real_404(self):
        response = self.client.get('/404/')
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Back to Home', status_code=404)
        self.assertContains(response, 'Browse Books', status_code=404)

    @override_settings(DEBUG=False)
    def test_unknown_url_and_missing_book(self):
        for path in ['/this-page-does-not-exist/', '/books/book-that-does-not-exist/']:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertTemplateUsed(response, '404.html')
