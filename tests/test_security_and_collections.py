import re

from app import db
from app.models import Collection, Snippet


def _extract_csrf(html: str) -> str:
    # Works for: <input type="hidden" name="csrf_token" value="...">
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
    return resp


def test_strips_csrf_token_query_param(client):
    r = client.get("/index?csrf_token=abc123&x=1", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert r.headers["Location"].endswith("/index?x=1")


def test_delete_collection_requires_csrf(client, app):
    _login(client)

    with app.app_context():
        col = Collection(name="Test", user_id=1)
        db.session.add(col)
        db.session.commit()
        cid = col.id

    # Missing CSRF should be rejected
    r = client.post(f"/collection/{cid}/delete", data={}, follow_redirects=False)
    assert r.status_code == 400

    # With CSRF should redirect
    page = client.get("/collections")
    token = _extract_csrf(page.get_data(as_text=True))
    ok = client.post(
        f"/collection/{cid}/delete",
        data={"csrf_token": token},
        follow_redirects=False,
    )
    assert ok.status_code in (302, 303)


def test_collection_partial_snippet_list(client, app):
    _login(client)

    with app.app_context():
        col = Collection(name="C1", user_id=1)
        db.session.add(col)
        db.session.commit()
        sn = Snippet(title="S1", code="print('hi')", description="", user_id=1, language="python", collection_id=col.id)
        db.session.add(sn)
        db.session.commit()
        cid = col.id

    r = client.get(f"/collection/{cid}?partial=1")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "snippet-item" in body

