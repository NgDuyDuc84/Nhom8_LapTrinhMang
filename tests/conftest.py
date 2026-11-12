"""Mọi test đều có CSDL riêng, kể cả test chỉ mock một phần repository."""
import pytest
from db import database


@pytest.fixture(autouse=True)
def protect_user_database(monkeypatch, tmp_path):
    for name in ("NETGUARD_TELEGRAM_TOKEN", "NETGUARD_TELEGRAM_CHAT_ID", "NETGUARD_ZALO_ACCESS_TOKEN", "NETGUARD_ZALO_USER_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NETGUARD_NOTIFICATIONS_ENABLED", "0")
    database.close()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "isolated.db"))
    yield
    database.close()
