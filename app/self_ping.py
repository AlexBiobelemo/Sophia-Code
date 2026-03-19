from __future__ import annotations

import os
from urllib.parse import urljoin


_started = False
_leader_lock_cm = None


def _env_truthy(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def start_self_ping(app) -> None:
    """
    Optional keep-alive self-ping.

    This is disabled by default locally, and auto-enabled on Render when
    RENDER_EXTERNAL_URL is present (can be overridden via env vars).

    Env vars:
      - SELF_PING_ENABLED=1/0 (default: auto on Render)
      - SELF_PING_LEADER=1/0  (optional; default: auto-elect leader via lock)
      - SELF_PING_LOCK_PATH=/tmp/sophia-self-ping.lock (optional)
      - SELF_PING_URL=https://your-app.onrender.com  (or rely on RENDER_EXTERNAL_URL)
      - SELF_PING_PATH=/health (optional)
      - SELF_PING_INTERVAL_MINUTES=12 (optional)
    """
    global _started
    if _started:
        return

    on_render = bool((os.environ.get("RENDER_EXTERNAL_URL") or "").strip())
    enabled = _env_truthy("SELF_PING_ENABLED", "1" if on_render else "0")
    if not enabled:
        return

    # In multi-worker deployments, starting a scheduler per worker can cause a burst of pings.
    # Default behavior: auto-elect a leader via a best-effort file lock to avoid multi-worker bursts.
    leader_override = os.environ.get("SELF_PING_LEADER")
    is_leader = _env_truthy("SELF_PING_LEADER", "0") if leader_override is not None else None
    if is_leader is None:
        lock_path = os.environ.get("SELF_PING_LOCK_PATH") or "/tmp/sophia-self-ping.lock"
        try:
            from app.utils.process_lock import single_instance_lock
        except Exception:  # pragma: no cover
            single_instance_lock = None

        if single_instance_lock is None:
            app.logger.info("Self-ping enabled but leader election unavailable; skipping.")
            return

        global _leader_lock_cm
        _leader_lock_cm = single_instance_lock(lock_path)
        acquired = False
        try:
            acquired = bool(_leader_lock_cm.__enter__())
        except Exception:
            acquired = False
        if not acquired:
            try:
                _leader_lock_cm.__exit__(None, None, None)
            except Exception:
                pass
            _leader_lock_cm = None
            return
        is_leader = True

    if not is_leader:
        app.logger.info("Self-ping enabled but this worker is not leader; skipping.")
        return

    base_url = (os.environ.get("SELF_PING_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").strip()
    if not base_url:
        app.logger.warning("Self-ping enabled but no SELF_PING_URL/RENDER_EXTERNAL_URL set; skipping.")
        return

    if base_url.startswith("http://") and _env_truthy("SELF_PING_FORCE_HTTPS", "1"):
        base_url = "https://" + base_url[len("http://") :]
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    path = (os.environ.get("SELF_PING_PATH") or "/health").strip() or "/health"
    ping_url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))

    try:
        interval_minutes = int(os.environ.get("SELF_PING_INTERVAL_MINUTES", "12"))
    except ValueError:
        interval_minutes = 12

    try:
        timeout_seconds = float(os.environ.get("SELF_PING_TIMEOUT_SECONDS", "6"))
    except ValueError:
        timeout_seconds = 6.0

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        import requests
    except Exception as e:  # pragma: no cover
        app.logger.warning(f"Self-ping enabled but deps missing: {e}")
        return

    def ping_self():
        try:
            requests.get(ping_url, timeout=timeout_seconds, headers={"User-Agent": "sophia-self-ping/1.0"})
        except Exception:
            return

    scheduler = BackgroundScheduler(daemon=True, timezone="UTC")
    scheduler.add_job(ping_self, "interval", minutes=interval_minutes, max_instances=1, coalesce=True)
    scheduler.start()

    _started = True
    app.logger.info(f"Self-ping scheduled every {interval_minutes} min to {ping_url}")
