"""HTTP adapter có timeout; không đưa token/URL bí mật vào ngoại lệ hoặc log."""
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


class NotificationError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


def post_json(url, payload, headers=None):
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode(),
                      headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read(1_000_000))
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise NotificationError(f"Dịch vụ thông báo trả HTTP {code}.", code == 429 or code >= 500) from None
    except (URLError, OSError, ValueError):
        raise NotificationError("Không kết nối/đọc được dịch vụ thông báo.", retryable=True) from None
