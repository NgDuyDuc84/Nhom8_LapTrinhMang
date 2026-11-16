"""Mọi test đều có CSDL riêng, kể cả test chỉ mock một phần repository."""
import pytest
from db import database


@pytest.fixture(autouse=True)
def protect_user_database(monkeypatch, tmp_path):
    database.close()
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "isolated.db"))
    yield
    database.close()
