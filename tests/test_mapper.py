import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thai_pua import ROOT, convert, preview_html, write_new
from thai_font_mapper import load_mapping, make_pattern, map_text


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_mapping(ROOT / 'assets/Mapping.json')
        cls.chars = set((ROOT / 'assets/Char.txt').read_text(encoding='utf-8'))

    def test_bom_and_mixed_newlines(self):
        for bom in (b'', b'\xef\xbb\xbf'):
            data = bom + 'กุ้ง\r\nปู่\nน้ำ\rผู้กล้า'.encode()
            result, _ = convert(data, self.mapping, self.chars)
            self.assertEqual(result.startswith(b'\xef\xbb\xbf'), bool(bom))
            self.assertEqual(result.count(b'\r'), 2)
            self.assertEqual(result.count(b'\n'), 2)
            self.assertEqual(len(result.decode('utf-8-sig').splitlines()), 4)

    def test_longest_match(self):
        m = {'ก': '\ue000', 'กั': '\ue001', 'กั่': '\ue002'}
        self.assertEqual(map_text('กั่กั', m, make_pattern(m)), '\ue002\ue001')

    def test_sara_am(self):
        pattern = make_pattern(self.mapping)
        self.assertEqual(map_text('น้ำ', self.mapping, pattern), map_text('น้ํา', self.mapping, pattern))

    def test_tags_and_placeholders(self):
        s = '[IT]<br>%s %1$s %% {name} $$VALUE$$\tกุ้ง'
        result, _ = convert(s.encode(), self.mapping, self.chars)
        self.assertTrue(result.decode().startswith(s[:s.index('ก')]))

    def test_unsupported_rejected(self):
        with self.assertRaises(ValueError):
            convert('😀'.encode(), self.mapping, self.chars)

    def test_invalid_thai_rejected(self):
        with self.assertRaises(ValueError):
            convert('่'.encode(), self.mapping, self.chars)

    def test_double_mapping_rejected(self):
        with self.assertRaises(ValueError):
            convert('\uf000'.encode(), self.mapping, self.chars)

    def test_utf16_rejected(self):
        with self.assertRaises((ValueError, UnicodeError)):
            convert('hello'.encode('utf-16'), self.mapping, self.chars)

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'out.txt'
            p.write_bytes(b'original')
            with self.assertRaises(FileExistsError):
                write_new(p, b'new')
            self.assertEqual(p.read_bytes(), b'original')

    def test_preview_escapes_html(self):
        page = preview_html('<script>alert(1)</script>', '<img>')
        self.assertNotIn(b'<script>', page)
        self.assertIn(b'&lt;img&gt;', page)

    def test_asset_checksums(self):
        import hashlib
        import json
        manifest = json.loads((ROOT / 'assets/SHA256.json').read_text(encoding='utf-8'))
        for name, expected in manifest.items():
            self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_preview_does_not_replace_user_words(self):
        self.assertIn(b'>MAPPED SOURCE</pre>', preview_html('MAPPED SOURCE', 'SOURCE MAPPED'))


if __name__ == '__main__':
    unittest.main()
