"""Đọc các record mDNS cần dùng, không khởi tạo hệ thống socket của Scapy."""
import socket
import struct


def read_name(payload: bytes, offset: int) -> tuple[str, int]:
    labels, visited = [], set()
    resume = None
    total = 0
    for _ in range(128):
        if offset in visited or not 0 <= offset < len(payload):
            raise ValueError("Tên DNS bị cắt hoặc có vòng lặp")
        visited.add(offset)
        size = payload[offset]
        if size & 0xC0 == 0xC0:
            if offset + 1 >= len(payload):
                raise ValueError("Con trỏ DNS bị cắt")
            if resume is None:
                resume = offset + 2
            offset = ((size & 0x3F) << 8) | payload[offset + 1]
            continue
        if size > 63:
            raise ValueError("Nhãn DNS không hợp lệ")
        offset += 1
        if size == 0:
            return ".".join(labels) + ".", resume if resume is not None else offset
        if offset + size > len(payload):
            raise ValueError("Nhãn DNS bị cắt")
        total += size + 1
        if total > 254:
            raise ValueError("Tên DNS quá dài")
        labels.append(payload[offset:offset + size].decode("utf-8", errors="replace"))
        offset += size
    raise ValueError("Tên DNS quá phức tạp")


def records(payload: bytes):
    _, _, questions, answers, authority, additional = struct.unpack_from("!6H", payload)
    if questions > 16 or answers + authority + additional > 128:
        raise ValueError("Quá nhiều record DNS")
    offset = 12
    for _ in range(questions):
        _, offset = read_name(payload, offset)
        offset += 4
        if offset > len(payload):
            raise ValueError("Câu hỏi DNS bị cắt")
    result = []
    for _ in range(answers + authority + additional):
        name, offset = read_name(payload, offset)
        kind, klass, ttl, size = struct.unpack_from("!HHIH", payload, offset)
        offset += 10
        end = offset + size
        if end > len(payload):
            raise ValueError("Record DNS bị cắt")
        value = None
        if kind == 1 and size == 4:
            value = socket.inet_ntoa(payload[offset:end])
        elif kind in (12, 33):
            start = offset + (6 if kind == 33 else 0)
            if start >= end:
                raise ValueError("Tên record DNS bị cắt")
            value, consumed = read_name(payload, start)
            if consumed != end:
                raise ValueError("Độ dài tên record DNS không hợp lệ")
        elif kind == 16:
            value = []
            while offset < end:
                length = payload[offset]
                offset += 1
                if offset + length > end:
                    raise ValueError("TXT DNS bị cắt")
                value.append(payload[offset:offset + length])
                offset += length
        result.append((name, kind, klass, ttl, value))
        offset = end
    return result


def query(ident: int, name: str, kind: int) -> bytes:
    labels = [label.encode("utf-8") for label in name.rstrip(".").split(".")]
    if any(not label or len(label) > 63 for label in labels) or sum(len(label) + 1 for label in labels) > 254:
        raise ValueError("Tên truy vấn DNS không hợp lệ")
    encoded = b"".join(bytes([len(label)]) + label for label in labels) + b"\0"
    return struct.pack("!6H", ident, 0, 1, 0, 0, 0) + encoded + struct.pack("!HH", kind, 1)
