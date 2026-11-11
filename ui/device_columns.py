"""Chỉ số cột dùng chung cho bảng thiết bị và delegate."""

from enum import IntEnum


class DeviceColumn(IntEnum):
    NAME = 0
    TYPE = 1
    MANUFACTURER = 2
    STATUS = 3
    TRUSTED = 4
    LAST_SEEN = 5
    NOTE = 6
    MAC = 7
    IP = 8
