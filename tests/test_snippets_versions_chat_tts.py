import re
import sys
import types

import pytest

from app import db
from app.models import ChatMessage, ChatSession, Collection, Snippet, SnippetVersion


def _extract_csrf(html: str) -> str:
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    assert m, "CSRF token not found in HTML"
    return m.group(1)


def _login(client):
    r = client.get("/login")
    token = _extract_csrf(r.get_data(as_text=True))
    resp = client.post(
        "/login",
        data={"username": "alice", "password": "password123!", "csrf_token": token},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)


def _csrf_header(client, page_path: str = "/index") -> dict:
    r = client.get(page_path)
    token = _extract_csrf(r.get_data(as_text=True))
    return {"X-CSRFToken": token}


def test_update_code_endpoint_creates_version(client, monkeypatch, app):
    _login(client)
    monkeypatch.setattr(Snippet, "generate_and_set_embedding", lambda self: None)
    with app.app_context():
        col = Collection(name="C1", user_id=1)
        db.session.add(col)
        db.session.commit()
        snip = Snippet(
            title="S1",
            code="print('a')",
            description="",
            user_id=1,
            language="python",
            collection_id=col.id,
        )
        db.session.add(snip)
        db.session.commit()
        sid = snip.id

        assert SnippetVersion.query.filter_by(snippet_id=sid).count() == 0

    h = _csrf_header(client, "/collections")
    r = client.post(
        f"/snippet/{sid}/update_code",
        json={"code": "print('b')\n"},
        headers=h,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data and data.get("success") is True

    with app.app_context():
        updated = db.session.get(Snippet, sid)
        assert updated.code.strip() == "print('b')"
        assert SnippetVersion.query.filter_by(snippet_id=sid).count() == 1


def test_version_diff_page_renders(client, app):
    _login(client)
    with app.app_context():
        snip = Snippet(title="S1", code="print('a')", description="", user_id=1, language="python")
        db.session.add(snip)
        db.session.commit()
        ver = SnippetVersion(snippet_id=snip.id, title=snip.title, description="", code="print('old')", language="python")
        db.session.add(ver)
        db.session.commit()
        vid = ver.id

    r = client.get(f"/snippet/version/{vid}/diff")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Version Diff" in body


def test_chat_send_persists_messages_and_returns_answer(client, monkeypatch, app):
    _login(client)

    def fake_answer(system, history, user_msg):
        assert "Sophia" in system
        return f"Echo: {user_msg}"

    import app.routes as routes

    monkeypatch.setattr(routes.ai_services, "chat_answer", fake_answer)

    h = _csrf_header(client, "/chat")
    r = client.post(
        "/api/chat/send",
        json={"session_id": None, "message": "Hello"},
        headers=h,
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["answer"] == "Echo: Hello"
    sid = data["session_id"]

    with app.app_context():
        s = db.session.get(ChatSession, sid)
        assert s is not None
        msgs = ChatMessage.query.filter_by(session_id=sid).order_by(ChatMessage.created_at.asc()).all()
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[1].content == "Echo: Hello"


def test_tts_endpoint_uses_stubbed_gtts(client, monkeypatch):
    _login(client)

    class FakeTTS:
        def __init__(self, text: str, lang: str = "en"):
            self.text = text
            self.lang = lang

        def write_to_fp(self, fp):
            fp.write(b"ID3FAKE")

    fake_mod = types.SimpleNamespace(gTTS=FakeTTS)
    monkeypatch.setitem(sys.modules, "gtts", fake_mod)

    h = _csrf_header(client, "/chat")
    r = client.post("/api/tts", json={"text": "Hello world", "lang": "en"}, headers=h)
    assert r.status_code == 200
    assert r.mimetype == "audio/mpeg"
    assert r.data.startswith(b"ID3")
