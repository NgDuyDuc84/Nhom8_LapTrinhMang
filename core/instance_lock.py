"""Khóa tiến trình giám sát; OS tự nhả khóa khi tiến trình kết thúc."""
from pathlib import Path
import os


class InstanceLock:
    def __init__(self, database):
        self.path = Path(database).resolve().with_suffix(".lock")
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        try:
            handle.seek(0, 2)
            if not handle.tell():
                handle.write(b"1")
                handle.flush()
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError("NetGuard đang được giám sát bởi một tiến trình khác. Hãy mở cửa sổ đang chạy hoặc thoát bản đó trước.") from exc
        self.file = handle

    def release(self):
        if self.file:
            self.file.close()
            self.file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()
