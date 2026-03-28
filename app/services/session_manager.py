from collections import defaultdict
from threading import Lock


class SessionCounter:
    def __init__(self) -> None:
        self._counts: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def get(self, session_id: str) -> int:
        with self._lock:
            return self._counts.get(session_id, 0)

    def increment(self, session_id: str) -> int:
        with self._lock:
            self._counts[session_id] += 1
            return self._counts[session_id]
