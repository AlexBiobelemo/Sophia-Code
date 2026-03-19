from __future__ import annotations

import argparse
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Common SQLite datetime representations:
    # - "2026-03-19 21:01:26.409123"
    # - "2026-03-19 21:01:26"
    # - ISO strings
    try:
        return datetime.fromisoformat(s.replace(" ", "T"))
    except Exception:
        return None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def _rows(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> Iterable[sqlite3.Row]:
    cur = conn.execute(sql, params)
    for row in cur.fetchall():
        yield row


def _scalar(conn: sqlite3.Connection, sql: str, params: Tuple[Any, ...] = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


@dataclass(frozen=True)
class ImportCounts:
    collections: int = 0
    snippets: int = 0
    snippet_versions: int = 0
    notes: int = 0
    chat_sessions: int = 0
    chat_messages: int = 0
    multi_step_results: int = 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import/merge a Sophia SQLite database into the current database for a specific user."
    )
    parser.add_argument("--source-db", required=True, help="Path to the source SQLite DB (e.g. ./old/app.db)")
    parser.add_argument("--source-user-email", required=True, help="Email of the user in the source DB to import")
    parser.add_argument(
        "--target-user-email",
        default=None,
        help="Email of the user in the target DB to receive imported data (defaults to source email)",
    )
    parser.add_argument(
        "--target-database-url",
        default=None,
        help="SQLAlchemy database URL for the target (defaults to env DATABASE_URL / config default)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print what would be imported without writing")

    args = parser.parse_args()
    source_db_path = Path(args.source_db).expanduser().resolve()
    if not source_db_path.exists():
        raise SystemExit(f"Source DB not found: {source_db_path}")

    target_user_email = (args.target_user_email or args.source_user_email).strip().lower()
    source_user_email = args.source_user_email.strip().lower()

    # Build a Flask app configured for the *target* DB.
    if args.target_database_url:
        os.environ["DATABASE_URL"] = args.target_database_url

    from app import create_app, db
    from config import Config
    from app.models import (
        User,
        Collection,
        Snippet,
        SnippetVersion,
        Note,
        ChatSession,
        ChatMessage,
        MultiStepResult,
    )

    app = create_app(Config)

    source_conn = sqlite3.connect(str(source_db_path))
    source_conn.row_factory = sqlite3.Row

    missing_tables = [
        t
        for t in [
            "user",
            "collection",
            "snippet",
            "snippet_version",
            "note",
            "chat_session",
            "chat_message",
            "multi_step_result",
        ]
        if not _table_exists(source_conn, t)
    ]
    if "user" in missing_tables:
        raise SystemExit("Source DB is missing required table: user")

    source_user_id = _scalar(source_conn, "SELECT id FROM user WHERE lower(email)=?", (source_user_email,))
    if source_user_id is None:
        raise SystemExit(f"Source user not found by email: {source_user_email}")

    with app.app_context():
        target_user = db.session.scalar(db.select(User).where(User.email.ilike(target_user_email)))
        if target_user is None:
            raise SystemExit(
                f"Target user not found in target DB: {target_user_email}. Create the account first, then re-run."
            )

        def unique_collection_name(base: str, parent_id: Optional[int]) -> str:
            name = base.strip() or "Imported Collection"
            suffix = 0
            while True:
                candidate = name if suffix == 0 else f"{name} (imported {suffix})"
                exists = db.session.scalar(
                    db.select(Collection).where(
                        Collection.user_id == target_user.id,
                        Collection.parent_id == parent_id,
                        Collection.name == candidate,
                    )
                )
                if not exists:
                    return candidate
                suffix += 1

        collection_id_map: Dict[int, int] = {}
        snippet_id_map: Dict[int, int] = {}

        counts = ImportCounts()

        # Collections (preserve hierarchy)
        if "collection" not in missing_tables:
            source_collections = list(
                _rows(
                    source_conn,
                    'SELECT id, name, parent_id, "order", timestamp FROM collection WHERE user_id=? ORDER BY parent_id, timestamp',
                    (source_user_id,),
                )
            )
            remaining = source_collections[:]
            progressed = True
            while remaining and progressed:
                progressed = False
                next_remaining = []
                for row in remaining:
                    src_id = int(row["id"])
                    src_parent = row["parent_id"]
                    if src_parent is not None and int(src_parent) not in collection_id_map:
                        next_remaining.append(row)
                        continue

                    dst_parent = None
                    if src_parent is not None:
                        dst_parent = collection_id_map[int(src_parent)]

                    col = Collection(
                        name=unique_collection_name(row["name"] or "Imported Collection", dst_parent),
                        order=int(row["order"] or 0),
                        user_id=target_user.id,
                        parent_id=dst_parent,
                    )
                    ts = _parse_dt(row["timestamp"])
                    if ts is not None:
                        col.timestamp = ts
                    if not args.dry_run:
                        db.session.add(col)
                        db.session.flush()
                        collection_id_map[src_id] = int(col.id)
                    else:
                        collection_id_map[src_id] = -1
                    counts = ImportCounts(
                        collections=counts.collections + 1,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions,
                        notes=counts.notes,
                        chat_sessions=counts.chat_sessions,
                        chat_messages=counts.chat_messages,
                        multi_step_results=counts.multi_step_results,
                    )
                    progressed = True
                remaining = next_remaining

        # Snippets
        if "snippet" not in missing_tables:
            for row in _rows(
                source_conn,
                "SELECT id, title, code, description, timestamp, tags, collection_id, language FROM snippet WHERE user_id=? ORDER BY timestamp",
                (source_user_id,),
            ):
                src_id = int(row["id"])
                src_collection_id = row["collection_id"]
                dst_collection_id = None
                if src_collection_id is not None and int(src_collection_id) in collection_id_map and not args.dry_run:
                    dst_collection_id = collection_id_map[int(src_collection_id)]

                snip = Snippet(
                    title=row["title"],
                    code=row["code"],
                    description=row["description"],
                    user_id=target_user.id,
                    tags=row["tags"],
                    collection_id=dst_collection_id,
                    language=row["language"] or "python",
                )
                ts = _parse_dt(row["timestamp"])
                if ts is not None:
                    snip.timestamp = ts

                if not args.dry_run:
                    db.session.add(snip)
                    db.session.flush()
                    snippet_id_map[src_id] = int(snip.id)
                else:
                    snippet_id_map[src_id] = -1

                counts = ImportCounts(
                    collections=counts.collections,
                    snippets=counts.snippets + 1,
                    snippet_versions=counts.snippet_versions,
                    notes=counts.notes,
                    chat_sessions=counts.chat_sessions,
                    chat_messages=counts.chat_messages,
                    multi_step_results=counts.multi_step_results,
                )

        # Snippet versions
        if "snippet_version" not in missing_tables and snippet_id_map:
            for row in _rows(
                source_conn,
                "SELECT snippet_id, title, description, code, language, tags, created_at FROM snippet_version WHERE snippet_id IN ({}) ORDER BY created_at".format(
                    ",".join(["?"] * len(snippet_id_map))
                ),
                tuple(snippet_id_map.keys()),
            ):
                src_snippet_id = int(row["snippet_id"])
                if src_snippet_id not in snippet_id_map:
                    continue
                if args.dry_run:
                    counts = ImportCounts(
                        collections=counts.collections,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions + 1,
                        notes=counts.notes,
                        chat_sessions=counts.chat_sessions,
                        chat_messages=counts.chat_messages,
                        multi_step_results=counts.multi_step_results,
                    )
                    continue

                ver = SnippetVersion(
                    snippet_id=snippet_id_map[src_snippet_id],
                    title=row["title"],
                    description=row["description"],
                    code=row["code"],
                    language=row["language"] or "python",
                    tags=row["tags"],
                )
                ts = _parse_dt(row["created_at"])
                if ts is not None:
                    ver.created_at = ts
                db.session.add(ver)

                counts = ImportCounts(
                    collections=counts.collections,
                    snippets=counts.snippets,
                    snippet_versions=counts.snippet_versions + 1,
                    notes=counts.notes,
                    chat_sessions=counts.chat_sessions,
                    chat_messages=counts.chat_messages,
                    multi_step_results=counts.multi_step_results,
                )

        # Notes
        if "note" not in missing_tables:
            for row in _rows(
                source_conn,
                "SELECT title, content, timestamp FROM note WHERE user_id=? ORDER BY timestamp",
                (source_user_id,),
            ):
                if args.dry_run:
                    counts = ImportCounts(
                        collections=counts.collections,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions,
                        notes=counts.notes + 1,
                        chat_sessions=counts.chat_sessions,
                        chat_messages=counts.chat_messages,
                        multi_step_results=counts.multi_step_results,
                    )
                    continue
                note = Note(title=row["title"], content=row["content"], user_id=target_user.id)
                ts = _parse_dt(row["timestamp"])
                if ts is not None:
                    note.timestamp = ts
                db.session.add(note)
                counts = ImportCounts(
                    collections=counts.collections,
                    snippets=counts.snippets,
                    snippet_versions=counts.snippet_versions,
                    notes=counts.notes + 1,
                    chat_sessions=counts.chat_sessions,
                    chat_messages=counts.chat_messages,
                    multi_step_results=counts.multi_step_results,
                )

        # Chat sessions + messages
        chat_session_id_map: Dict[int, int] = {}
        if "chat_session" not in missing_tables and "chat_message" not in missing_tables:
            for row in _rows(
                source_conn,
                "SELECT id, title, created_at, updated_at FROM chat_session WHERE user_id=? ORDER BY updated_at",
                (source_user_id,),
            ):
                src_session_id = int(row["id"])
                if args.dry_run:
                    chat_session_id_map[src_session_id] = -1
                    counts = ImportCounts(
                        collections=counts.collections,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions,
                        notes=counts.notes,
                        chat_sessions=counts.chat_sessions + 1,
                        chat_messages=counts.chat_messages,
                        multi_step_results=counts.multi_step_results,
                    )
                    continue

                sess = ChatSession(user_id=target_user.id, title=row["title"] or "Imported Chat")
                created_at = _parse_dt(row["created_at"])
                updated_at = _parse_dt(row["updated_at"])
                if created_at is not None:
                    sess.created_at = created_at
                if updated_at is not None:
                    sess.updated_at = updated_at
                db.session.add(sess)
                db.session.flush()
                chat_session_id_map[src_session_id] = int(sess.id)
                counts = ImportCounts(
                    collections=counts.collections,
                    snippets=counts.snippets,
                    snippet_versions=counts.snippet_versions,
                    notes=counts.notes,
                    chat_sessions=counts.chat_sessions + 1,
                    chat_messages=counts.chat_messages,
                    multi_step_results=counts.multi_step_results,
                )

            if chat_session_id_map:
                for row in _rows(
                    source_conn,
                    "SELECT session_id, role, content, created_at FROM chat_message WHERE session_id IN ({}) ORDER BY created_at".format(
                        ",".join(["?"] * len(chat_session_id_map))
                    ),
                    tuple(chat_session_id_map.keys()),
                ):
                    src_session_id = int(row["session_id"])
                    if src_session_id not in chat_session_id_map:
                        continue
                    if args.dry_run:
                        counts = ImportCounts(
                            collections=counts.collections,
                            snippets=counts.snippets,
                            snippet_versions=counts.snippet_versions,
                            notes=counts.notes,
                            chat_sessions=counts.chat_sessions,
                            chat_messages=counts.chat_messages + 1,
                            multi_step_results=counts.multi_step_results,
                        )
                        continue

                    msg = ChatMessage(
                        session_id=chat_session_id_map[src_session_id],
                        role=row["role"] or "assistant",
                        content=row["content"] or "",
                    )
                    ts = _parse_dt(row["created_at"])
                    if ts is not None:
                        msg.created_at = ts
                    db.session.add(msg)
                    counts = ImportCounts(
                        collections=counts.collections,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions,
                        notes=counts.notes,
                        chat_sessions=counts.chat_sessions,
                        chat_messages=counts.chat_messages + 1,
                        multi_step_results=counts.multi_step_results,
                    )

        # Multi-step results
        if "multi_step_result" not in missing_tables:
            for row in _rows(
                source_conn,
                "SELECT result_id, prompt, test_cases, status, error_message, layer1_architecture, layer2_coder, layer3_tester, layer4_refiner, final_code, final_tests, final_explanation, processing_time, timestamp, completed_at FROM multi_step_result WHERE user_id=? ORDER BY timestamp",
                (source_user_id,),
            ):
                if args.dry_run:
                    counts = ImportCounts(
                        collections=counts.collections,
                        snippets=counts.snippets,
                        snippet_versions=counts.snippet_versions,
                        notes=counts.notes,
                        chat_sessions=counts.chat_sessions,
                        chat_messages=counts.chat_messages,
                        multi_step_results=counts.multi_step_results + 1,
                    )
                    continue

                r = MultiStepResult(
                    result_id=row["result_id"],
                    user_id=target_user.id,
                    prompt=row["prompt"],
                    test_cases=row["test_cases"],
                    status=row["status"] or "completed",
                    error_message=row["error_message"],
                    layer1_architecture=row["layer1_architecture"],
                    layer2_coder=row["layer2_coder"],
                    layer3_tester=row["layer3_tester"],
                    layer4_refiner=row["layer4_refiner"],
                    final_code=row["final_code"],
                    final_tests=row["final_tests"],
                    final_explanation=row["final_explanation"],
                    processing_time=row["processing_time"],
                )
                ts = _parse_dt(row["timestamp"])
                if ts is not None:
                    r.timestamp = ts
                done = _parse_dt(row["completed_at"])
                if done is not None:
                    r.completed_at = done
                db.session.add(r)
                counts = ImportCounts(
                    collections=counts.collections,
                    snippets=counts.snippets,
                    snippet_versions=counts.snippet_versions,
                    notes=counts.notes,
                    chat_sessions=counts.chat_sessions,
                    chat_messages=counts.chat_messages,
                    multi_step_results=counts.multi_step_results + 1,
                )

        if args.dry_run:
            print("Dry run (no writes). Would import:")
            print(f"  Collections:       {counts.collections}")
            print(f"  Snippets:          {counts.snippets}")
            print(f"  Snippet versions:  {counts.snippet_versions}")
            print(f"  Notes:             {counts.notes}")
            print(f"  Chat sessions:     {counts.chat_sessions}")
            print(f"  Chat messages:     {counts.chat_messages}")
            print(f"  Multi-step results:{counts.multi_step_results}")
            return 0

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        print("Import completed:")
        print(f"  Collections:       {counts.collections}")
        print(f"  Snippets:          {counts.snippets}")
        print(f"  Snippet versions:  {counts.snippet_versions}")
        print(f"  Notes:             {counts.notes}")
        print(f"  Chat sessions:     {counts.chat_sessions}")
        print(f"  Chat messages:     {counts.chat_messages}")
        print(f"  Multi-step results:{counts.multi_step_results}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

