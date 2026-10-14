"""Native folder picker. Windows IFileOpenDialog; elsewhere picker-unavailable."""

from __future__ import annotations

import sys

from library.errors import fail


def pick_folder() -> str | None:
    if sys.platform != "win32":
        raise fail("picker-unavailable")
    try:
        return _windows_pick_folder()
    except OSError as exc:
        raise fail("picker-unavailable") from exc


def _windows_pick_folder() -> str | None:
    import ctypes
    from ctypes import wintypes

    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx.argtypes = [wintypes.LPVOID, wintypes.DWORD]
    ole32.CoInitializeEx.restype = ctypes.HRESULT
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    ole32.CoCreateInstance.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    ole32.CoCreateInstance.restype = ctypes.HRESULT
    ole32.CLSIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
    ole32.CLSIDFromString.restype = ctypes.HRESULT
    ole32.IIDFromString.argtypes = [wintypes.LPCWSTR, ctypes.c_void_p]
    ole32.IIDFromString.restype = ctypes.HRESULT

    class GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", wintypes.DWORD),
            ("Data2", wintypes.WORD),
            ("Data3", wintypes.WORD),
            ("Data4", wintypes.BYTE * 8),
        ]

    COINIT_APARTMENTTHREADED = 0x2
    CLSCTX_INPROC_SERVER = 0x1
    FOS_PICKFOLDERS = 0x20
    FOS_FORCEFILESYSTEM = 0x40
    SIGDN_FILESYSPATH = 0x80058000
    HRESULT_CANCELLED = 0x800704C7

    class IUnknownVtbl(ctypes.Structure):
        pass

    class IUnknown(ctypes.Structure):
        _fields_ = [("lpVtbl", ctypes.POINTER(IUnknownVtbl))]

    IUnknownVtbl._fields_ = [
        (
            "QueryInterface",
            ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.POINTER(IUnknown),
                ctypes.POINTER(GUID),
                ctypes.POINTER(ctypes.c_void_p),
            ),
        ),
        ("AddRef", ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.POINTER(IUnknown))),
        ("Release", ctypes.WINFUNCTYPE(wintypes.ULONG, ctypes.POINTER(IUnknown))),
    ]

    class IFileOpenDialogVtbl(ctypes.Structure):
        pass

    class IFileOpenDialog(ctypes.Structure):
        _fields_ = [("lpVtbl", ctypes.POINTER(IFileOpenDialogVtbl))]

    HWND = wintypes.HWND
    HRESULT = ctypes.HRESULT
    DWORD = wintypes.DWORD
    LPVOID = ctypes.c_void_p
    ULONG = wintypes.ULONG

    IFileOpenDialogVtbl._fields_ = [
        (
            "QueryInterface",
            ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)),
        ),
        ("AddRef", ctypes.WINFUNCTYPE(ULONG, ctypes.POINTER(IFileOpenDialog))),
        ("Release", ctypes.WINFUNCTYPE(ULONG, ctypes.POINTER(IFileOpenDialog))),
        ("Show", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), HWND)),
        ("SetFileTypes", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.UINT, LPVOID)),
        ("SetFileTypeIndex", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.UINT)),
        ("GetFileTypeIndex", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(wintypes.UINT))),
        ("Advise", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), LPVOID, ctypes.POINTER(DWORD))),
        ("Unadvise", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), DWORD)),
        ("SetOptions", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), DWORD)),
        ("GetOptions", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(DWORD))),
        ("SetDefaultFolder", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), LPVOID)),
        ("SetFolder", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), LPVOID)),
        ("GetFolder", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(LPVOID))),
        ("GetCurrentSelection", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(LPVOID))),
        ("SetFileName", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.LPCWSTR)),
        ("GetFileName", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(wintypes.LPWSTR))),
        ("SetTitle", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.LPCWSTR)),
        ("SetOkButtonLabel", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.LPCWSTR)),
        ("SetFileNameLabel", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.LPCWSTR)),
        ("GetResult", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(ctypes.POINTER(IUnknown)))),
        ("AddPlace", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), LPVOID, wintypes.UINT)),
        ("SetDefaultExtension", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), wintypes.LPCWSTR)),
        ("Close", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), HRESULT)),
        ("SetClientGuid", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(GUID))),
        ("ClearClientData", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog))),
        ("SetFilter", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), LPVOID)),
        ("GetResults", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(LPVOID))),
        ("GetSelectedItems", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IFileOpenDialog), ctypes.POINTER(LPVOID))),
    ]

    class IShellItemVtbl(ctypes.Structure):
        pass

    class IShellItem(ctypes.Structure):
        _fields_ = [("lpVtbl", ctypes.POINTER(IShellItemVtbl))]

    IShellItemVtbl._fields_ = [
        (
            "QueryInterface",
            ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), ctypes.POINTER(GUID), ctypes.POINTER(LPVOID)),
        ),
        ("AddRef", ctypes.WINFUNCTYPE(ULONG, ctypes.POINTER(IShellItem))),
        ("Release", ctypes.WINFUNCTYPE(ULONG, ctypes.POINTER(IShellItem))),
        ("BindToHandler", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), LPVOID, ctypes.POINTER(GUID), ctypes.POINTER(GUID), ctypes.POINTER(LPVOID))),
        ("GetParent", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), ctypes.POINTER(LPVOID))),
        ("GetDisplayName", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), ctypes.c_int, ctypes.POINTER(wintypes.LPWSTR))),
        ("GetAttributes", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), DWORD, ctypes.POINTER(DWORD))),
        ("Compare", ctypes.WINFUNCTYPE(HRESULT, ctypes.POINTER(IShellItem), LPVOID, DWORD, ctypes.POINTER(ctypes.c_int))),
    ]

    clsid = GUID()
    iid_dialog = GUID()
    ole32.CLSIDFromString("{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}", ctypes.byref(clsid))
    ole32.IIDFromString("{D57C7288-D4AD-4768-BE02-9D969532D960}", ctypes.byref(iid_dialog))

    initialized = False
    hr = ole32.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr in (0, 1, 0x80010106):
        initialized = hr in (0, 1)
    else:
        raise fail("picker-unavailable")

    dialog_ptr = ctypes.c_void_p()
    item = None
    dialog = None
    try:
        hr = ole32.CoCreateInstance(
            ctypes.byref(clsid),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(iid_dialog),
            ctypes.byref(dialog_ptr),
        )
        if hr != 0 or not dialog_ptr.value:
            raise fail("picker-unavailable")
        dialog = ctypes.cast(dialog_ptr, ctypes.POINTER(IFileOpenDialog))
        vtbl = dialog.contents.lpVtbl.contents
        hr = vtbl.SetOptions(dialog, FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM)
        if hr != 0:
            raise fail("picker-unavailable")
        hr = vtbl.Show(dialog, None)
        if hr & 0xFFFFFFFF == HRESULT_CANCELLED or hr == 1:
            return None
        if hr != 0:
            raise fail("picker-unavailable")
        item_ptr = ctypes.POINTER(IUnknown)()
        hr = vtbl.GetResult(dialog, ctypes.byref(item_ptr))
        if hr != 0 or not item_ptr:
            raise fail("picker-unavailable")
        item = ctypes.cast(item_ptr, ctypes.POINTER(IShellItem))
        name = wintypes.LPWSTR()
        hr = item.contents.lpVtbl.contents.GetDisplayName(item, SIGDN_FILESYSPATH, ctypes.byref(name))
        if hr != 0 or not name:
            raise fail("picker-unavailable")
        path = name.value
        ctypes.windll.ole32.CoTaskMemFree(name)
        return path
    finally:
        if item is not None:
            item.contents.lpVtbl.contents.Release(item)
        if dialog is not None:
            dialog.contents.lpVtbl.contents.Release(dialog)
        if initialized:
            ole32.CoUninitialize()
