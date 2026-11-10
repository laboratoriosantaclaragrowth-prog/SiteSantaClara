import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools/vendor'))
from bs4 import BeautifulSoup


class CampaignPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = BeautifulSoup((ROOT / 'santa-clara-ate-voce/index.html').read_text(encoding='utf-8'), 'html.parser')

    def test_separate_page_and_identity(self):
        self.assertEqual(self.page.html['lang'], 'pt-BR')
        self.assertEqual(len(self.page.select('h1')), 1)
        self.assertIn('Santa Clara', self.page.h1.text)
        for text in ('Hermes', 'Pardini', 'CRM/MG 35635', 'Belo Horizonte', 'Vacinas'):
            self.assertNotIn(text, self.page.get_text())
        self.assertIsNotNone(self.page.select_one('meta[name="description"]'))

    def test_assets_and_links(self):
        for tag in self.page.select('img[src],script[src],link[href],a[href]'):
            href = tag.get('src') or tag['href']
            url = urlsplit(href)
            if url.netloc:
                self.assertNotIn('pardini', url.netloc)
                if url.netloc == 'wa.me':
                    self.assertEqual(url.path, '/5533987521448')
                    self.assertIn('text', parse_qs(url.query))
                continue
            if url.path:
                target = ROOT / url.path.lstrip('/')
                self.assertTrue(target.exists(), href)
            elif url.fragment:
                self.assertIsNotNone(self.page.find(id=url.fragment), href)
        self.assertFalse(self.page.select('iframe,script[src*="google"],script[src*="jquery"]'))

    def test_controls(self):
        self.assertEqual(len(self.page.select('[data-benefit]')), 3)
        self.assertEqual(len(self.page.select('[data-benefit]:not([hidden])')), 1)
        for button in self.page.select('.accordion-button'):
            self.assertIsNotNone(self.page.select_one(button['data-bs-target']))
        self.assertIn('disponibilidade', self.page.select_one('#banner').get_text())


if __name__ == '__main__':
    unittest.main()
