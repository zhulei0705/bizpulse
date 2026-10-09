"""T10-A research-only evidence capture; never opens a writable business DB."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.services.extractor import fetch_public_page

OUT = ROOT.parent / 'docs' / 'reports' / 't10_a'


def capture(url: str) -> dict:
    stamp = datetime.now(timezone.utc).isoformat()
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    try:
        page = fetch_public_page(url)
        (OUT / 'raw').mkdir(parents=True, exist_ok=True)
        (OUT / 'raw' / f'{key}.html').write_text(page.html, encoding='utf-8')
        (OUT / 'raw' / f'{key}.txt').write_text(page.text, encoding='utf-8')
        soup = BeautifulSoup(page.html, 'html.parser')
        for element in soup(['script', 'style', 'noscript']):
            element.decompose()
        full_text = soup.get_text(' ', strip=True)
        (OUT / 'raw' / f'{key}.full.txt').write_text(full_text, encoding='utf-8')
        return dict(url=url, final_url=page.final_url, title=page.title,
                    collected_at=stamp, http_status=page.status_code,
                    text_path=f'raw/{key}.txt', html_path=f'raw/{key}.html',
                    full_text_path=f'raw/{key}.full.txt',
                    sha256=hashlib.sha256(page.text.encode()).hexdigest(),
                    text_length=len(page.text), status='CAPTURED')
    except Exception as exc:
        return dict(url=url, collected_at=stamp, status='FAILED', error=str(exc))


def baseline() -> dict:
    with sqlite3.connect(f'file:{ROOT / "data" / "bizpulse.db"}?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        tables = ['experiments', 'experiment_targets', 'interactions', 'quotes', 'experiment_outcomes']
        result = {t: [dict(r) for r in db.execute(f'SELECT * FROM {t} ORDER BY id')] for t in tables}
        return result


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1] == 'baseline':
        path = OUT / sys.argv[2]
        path.write_text(json.dumps(baseline(), ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        urls = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        rows = list(ThreadPoolExecutor(max_workers=4).map(capture, urls))
        path = OUT / sys.argv[2]
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
