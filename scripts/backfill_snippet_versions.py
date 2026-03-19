from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app, db  # noqa: E402
from app.models import Snippet, SnippetVersion  # noqa: E402


def main() -> int:
    app = create_app()
    created = 0
    scanned = 0
    with app.app_context():
        snippets = db.session.query(Snippet).all()
        for s in snippets:
            scanned += 1
            if s.versions.count() > 0:
                continue
            v = SnippetVersion(
                snippet_id=s.id,
                title=s.title,
                description=s.description,
                code=s.code,
                language=s.language,
                tags=s.tags,
                created_at=s.timestamp,
            )
            db.session.add(v)
            created += 1

        if created:
            db.session.commit()

    print(f"Backfill complete: scanned={scanned} created={created}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
