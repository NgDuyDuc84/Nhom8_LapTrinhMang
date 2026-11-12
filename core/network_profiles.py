"""Hồ sơ Network List Manager của Windows (không dùng NetworkGuid mặc định NDIS).

Vtable theo netlistmgr.h của Windows SDK. Chỉ gọi các getter và Release().
"""
import ctypes as C
from ctypes import wintypes as W
import logging
import uuid


class GUID(C.Structure):
    _fields_ = [("data1", W.DWORD), ("data2", W.WORD), ("data3", W.WORD), ("data4", C.c_ubyte*8)]

    @classmethod
    def parse(cls, value):
        return cls.from_buffer_copy(uuid.UUID(value).bytes_le)

    def __str__(self):
        return str(uuid.UUID(bytes_le=bytes(self)))


def _method(pointer, slot, result, *arguments):
    table = C.cast(pointer, C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(result, C.c_void_p, *arguments)(table[slot])


def _get(pointer, slot, *outputs):
    function = _method(pointer, slot, C.c_long, *(type(output) for output in outputs))
    status = function(pointer, *outputs)
    if status < 0:
        raise OSError(status & 0xffffffff, "Network List Manager")
    return status


def _release(pointer):
    if pointer.value:
        _method(pointer, 2, W.ULONG)(pointer)


def profiles_by_adapter():
    manager, enumeration = C.c_void_p(), C.c_void_p()
    initialized = False
    ole = None
    try:
        ole = C.WinDLL("ole32")
        ole.CoInitializeEx.argtypes = [C.c_void_p, W.DWORD]
        ole.CoInitializeEx.restype = C.c_long
        ole.CoUninitialize.argtypes = []
        ole.CoUninitialize.restype = None
        status = ole.CoInitializeEx(None, 2)
        initialized = status in (0, 1)
        if status < 0 and status != -2147417850:  # RPC_E_CHANGED_MODE: dùng apartment sẵn có.
            raise OSError(status & 0xffffffff, "CoInitializeEx")
        clsid = GUID.parse("DCB00C01-570F-4A9B-8D69-199FDBA5723B")
        iid = GUID.parse("DCB00000-570F-4A9B-8D69-199FDBA5723B")
        ole.CoCreateInstance.argtypes = [C.POINTER(GUID), C.c_void_p, W.DWORD, C.POINTER(GUID), C.POINTER(C.c_void_p)]
        ole.CoCreateInstance.restype = C.c_long
        status = ole.CoCreateInstance(C.byref(clsid), None, 23, C.byref(iid), C.byref(manager))
        if status < 0:
            raise OSError(status & 0xffffffff, "CoCreateInstance NetworkListManager")
        _get(manager, 9, C.pointer(enumeration))  # INetworkListManager.GetNetworkConnections
        profiles = {}
        for _ in range(256):
            connection, network = C.c_void_p(), C.c_void_p()
            fetched = W.ULONG()
            # IEnumNetworkConnections: IDispatch(7), _NewEnum(7), Next(8).
            next_method = _method(enumeration, 8, C.c_long, W.ULONG, C.POINTER(C.c_void_p), C.POINTER(W.ULONG))
            status = next_method(enumeration, 1, C.byref(connection), C.byref(fetched))
            if status < 0:
                raise OSError(status & 0xffffffff, "NLM Next")
            if not fetched.value:
                break
            try:
                connected = C.c_short()
                _get(connection, 9, C.pointer(connected))
                if not connected.value:
                    continue
                adapter, identifier = GUID(), GUID()
                _get(connection, 12, C.pointer(adapter))  # GetAdapterId
                _get(connection, 7, C.pointer(network))  # GetNetwork
                _get(network, 11, C.pointer(identifier))  # INetwork.GetNetworkId
                profiles[str(adapter)] = str(identifier)
            finally:
                _release(network)
                _release(connection)
        return profiles
    except (AttributeError, OSError, ValueError):
        logging.getLogger(__name__).exception("Không đọc được hồ sơ Network List Manager")
        return {}
    finally:
        _release(enumeration)
        _release(manager)
        if initialized and ole:
            ole.CoUninitialize()
