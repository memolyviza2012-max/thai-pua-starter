#!/usr/bin/env python3
"""Offline UTF-8/UTF-8-BOM Thai PUA conversion; never overwrite input files."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

from thai_font_mapper import audit, load_mapping, make_pattern, map_text

ROOT = Path(__file__).resolve().parent


def convert(data: bytes, mapping: dict[str, str], charset: set[str]) -> tuple[bytes, str]:
    """Keep BOM, exact newline sequences and physical line count; audit before writing."""
    bom = data.startswith(b'\xef\xbb\xbf')
    source = data.decode('utf-8-sig' if bom else 'utf-8', errors='strict')
    if '\x00' in source:
        raise ValueError('NUL detected: use exported UTF-8 text, not a game binary or UTF-16 file.')
    if any(0xE000 <= ord(c) <= 0xF8FF for c in source):
        raise ValueError('Input already contains PUA. Use the readable Thai original.')
    result = map_text(source, mapping, make_pattern(mapping))
    issues = audit(result, charset)
    if issues:
        raise ValueError('; '.join(issues))
    import re
    if re.findall(r'\r\n|\r|\n', source) != re.findall(r'\r\n|\r|\n', result):
        raise ValueError('Newline sequences changed.')
    assert len(source.splitlines(keepends=True)) == len(result.splitlines(keepends=True))
    return result.encode('utf-8-sig' if bom else 'utf-8'), source


def preview_html(source: str, mapped: str) -> bytes:
    """A local source-font preview, not a claim about native game rendering."""
    page = '''<!doctype html><html lang="th"><meta charset="utf-8">
<title>Thai PUA Starter — font preview</title><style>
@font-face{font-family:ThaiPUA;src:url('assets/ThaiPUAStarter-Bold.ttf')}
body{background:#10151e;color:#eaf0ff;max-width:960px;margin:40px auto;padding:20px;font-family:Tahoma,sans-serif}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1a2332;padding:24px;border-radius:12px}
.mapped{font-family:ThaiPUA;font-size:32px;line-height:1.8}
</style><h1>Thai PUA Starter</h1><p>ตัวอย่างฟอนต์ต้นทางบนเบราว์เซอร์ ไม่ใช่ผลการแสดงในเกม</p>
<h2>ข้อความไทยต้นฉบับ</h2><pre>SOURCE</pre><h2>PUA + ฟอนต์ที่ตรงกัน</h2><pre class="mapped">MAPPED</pre>
<p>หากในเกมสระขาด ให้ตรวจ atlas, glyph metrics, baseline และพื้นที่ตัดขอบด้วย</p></html>'''
    import re
    values = {'SOURCE': html.escape(source), 'MAPPED': html.escape(mapped)}
    return re.sub(r'SOURCE|MAPPED', lambda match: values[match.group()], page).encode('utf-8')


def write_new(path: Path, data: bytes) -> None:
    """Exclusive creation ensures even an existing empty output is protected."""
    with path.open('xb') as stream:
        stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Readable Thai UTF-8 .txt export')
    parser.add_argument('-o', '--output', required=True, type=Path)
    parser.add_argument('--preview', type=Path, help='New HTML file in the repository root')
    args = parser.parse_args()
    try:
        if args.input.suffix.lower() != '.txt' or args.output.suffix.lower() != '.txt':
            raise ValueError('Only .txt exports are accepted. Do not convert whole CSV/JSON/game archives.')
        paths = [args.output] + ([args.preview] if args.preview else [])
        if any(p.resolve() == args.input.resolve() or p.exists() for p in paths):
            raise ValueError('Output/preview must be new files, separate from input.')
        if args.preview and (args.preview.suffix.lower() != '.html' or args.preview.resolve().parent != ROOT):
            raise ValueError('Place the HTML preview in the repository root next to assets/.')
        if len({p.resolve() for p in paths}) != len(paths):
            raise ValueError('Output paths must be distinct.')
        mapping = load_mapping(ROOT / 'assets/Mapping.json')
        charset = set((ROOT / 'assets/Char.txt').read_text(encoding='utf-8').rstrip('\r\n'))
        data = args.input.read_bytes()
        result, source = convert(data, mapping, charset)
        write_new(args.output, result)
        if args.preview:
            write_new(args.preview, preview_html(source, result.decode('utf-8-sig')))
        print('OK — source unchanged; BOM and newline sequences preserved.')
        print('Output SHA-256:', hashlib.sha256(result).hexdigest())
        return 0
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
