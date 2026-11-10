import json
import re
import sys
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools/vendor'))
from bs4 import BeautifulSoup


class InformationalSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = [ROOT / 'index.html', *sorted((ROOT / 'exames').rglob('index.html'))]
        cls.documents = [BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser') for path in cls.files]

    def test_page_count_and_unique_metadata(self):
        self.assertEqual(len(self.files), 9)
        self.assertEqual(len({doc.title.text for doc in self.documents}), 9)
        self.assertEqual(len({doc.select_one('meta[name="description"]')['content'] for doc in self.documents}), 9)
        for doc in self.documents:
            self.assertEqual(len(doc.select('h1')), 1)

    def test_no_commerce(self):
        for doc in self.documents:
            self.assertNotRegex(doc.get_text(' ', strip=True).lower(), r'r\$|carrinho|orçamento|comprar|valor do exame')
            self.assertFalse(doc.select('[data-add-exam],#exam-search,[data-action="orcamento"]'))
            self.assertTrue(doc.select_one('script[src="/informational.js"]'))

    def test_local_links_and_assets(self):
        for path, doc in zip(self.files, self.documents):
            for tag in doc.select('a[href],img[src],script[src],link[href]'):
                href = tag.get('href') or tag.get('src')
                if tag.get('data-action'):
                    continue
                url = urlsplit(href)
                if url.scheme or url.netloc:
                    continue
                target = ROOT / url.path.lstrip('/') if url.path else path
                if target.is_dir():
                    target /= 'index.html'
                self.assertTrue(target.is_file(), f'{path}: missing {href}')
                if url.fragment:
                    target_doc = BeautifulSoup(target.read_text(encoding='utf-8'), 'html.parser')
                    self.assertIsNotNone(target_doc.find(id=url.fragment), f'{path}: invalid anchor {href}')

    def test_schema_and_contact_integrity(self):
        business = json.loads((ROOT / 'content/business.json').read_text(encoding='utf-8'))
        for doc in self.documents:
            schema = json.loads(doc.select_one('script[type="application/ld+json"]').string)
            self.assertEqual(schema['publisher']['address']['addressLocality'], 'Araçuaí')
            self.assertNotIn('reviewedBy', schema)
            if not business['address']:
                self.assertNotIn('streetAddress', schema['publisher']['address'])
                self.assertFalse(doc.select('iframe'))
            if not business['siteUrl']:
                self.assertFalse(doc.select('link[rel="canonical"]'))

    def test_exam_pages_have_static_content(self):
        for path, doc in zip(self.files, self.documents):
            if path.parent in {ROOT, ROOT / 'exames', ROOT / 'exames/aracuai'}:
                continue
            self.assertTrue(doc.select_one('.exam-article'))
            self.assertTrue(doc.select_one('#onde-estamos'))
            self.assertIn('Como se preparar?', doc.get_text())
            self.assertIn('MedlinePlus', doc.get_text())
            self.assertNotIn('conteúdo revisado', doc.get_text().lower())

    def test_conversion_paths(self):
        home = self.documents[0]
        self.assertIsNotNone(home.select_one('.conversion-hero h1'))
        self.assertIsNone(home.select_one('#slide-track'))
        self.assertEqual(len(home.select('#perguntas-frequentes details')), 5)
        for doc in self.documents:
            self.assertIsNotNone(doc.select_one('.mobile-contact-bar a[href^="https://wa.me/5533987521448"]'))
            self.assertIsNotNone(doc.select_one('a[href^="tel:"]'))
            self.assertIsNotNone(doc.select_one('a[href^="https://www.google.com/maps/dir/"]'))
            self.assertNotIn('Endereço completo: confirme', doc.get_text())
            self.assertNotIn('Mapa disponível após confirmação', doc.get_text())


if __name__ == '__main__':
    unittest.main()
