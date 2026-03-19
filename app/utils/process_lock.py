from __future__ import annotations

import os
from contextlib import contextmanager


@contextmanager
def single_instance_lock(lock_path: str):
    """
    Best-effort cross-platform lock to ensure a block runs once per machine/container.

    Yields:
      acquired (bool): True if lock acquired, False otherwise.
    """
    os.makedirs(os.path.dirname(lock_path) or ".", exist_ok=True)
    f = open(lock_path, "a+", encoding="utf-8")
    acquired = False
    try:
        try:
            import fcntl  # type: ignore

            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except Exception:
            try:
                import msvcrt  # type: ignore

                # Lock 1 byte at start of file
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                acquired = True
            except Exception:
                acquired = False

        yield acquired
    finally:
        if acquired:
            try:
                try:
                    import fcntl  # type: ignore

                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    import msvcrt  # type: ignore

                    f.seek(0)
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            except Exception:
                pass
        try:
            f.close()
        except Exception:
            pass

