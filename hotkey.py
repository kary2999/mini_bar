"""
Meowser — 全局快捷键（Carbon RegisterEventHotKey，无需权限）
支持多个热键动态注册/注销
"""

import ctypes
from ctypes import (
    c_uint32, c_int32, c_void_p, byref, Structure, CFUNCTYPE, POINTER, sizeof,
)
from Foundation import NSLog

_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")

kEventClassKeyboard = 0x6B657962
kEventHotKeyPressed = 5
kEventParamDirectObject = 0x2D2D2D2D
typeEventHotKeyID = 0x686B6964
noErr = 0


class EventTypeSpec(Structure):
    _fields_ = [("eventClass", c_uint32), ("eventKind", c_uint32)]


class EventHotKeyID(Structure):
    _fields_ = [("signature", c_uint32), ("id", c_uint32)]


_carbon.GetApplicationEventTarget.restype = c_void_p
_carbon.RegisterEventHotKey.argtypes = [
    c_uint32, c_uint32, EventHotKeyID, c_void_p, c_uint32, POINTER(c_void_p),
]
_carbon.RegisterEventHotKey.restype = c_int32
_carbon.UnregisterEventHotKey.argtypes = [c_void_p]
_carbon.UnregisterEventHotKey.restype = c_int32

EventHandlerProc = CFUNCTYPE(c_int32, c_void_p, c_void_p, c_void_p)
_carbon.InstallEventHandler.argtypes = [
    c_void_p, EventHandlerProc, c_uint32, POINTER(EventTypeSpec),
    c_void_p, POINTER(c_void_p),
]
_carbon.InstallEventHandler.restype = c_int32

_carbon.GetEventParameter.argtypes = [
    c_void_p, c_uint32, c_uint32, POINTER(c_uint32),
    c_uint32, POINTER(c_uint32), c_void_p,
]
_carbon.GetEventParameter.restype = c_int32


class HotkeyManager:
    def __init__(self):
        self._handler_installed = False
        self._handler_proc = None
        self._callbacks = {}   # id -> callback
        self._refs = {}        # id -> hotkey ref
        self._next_id = 1

    def _install_handler(self):
        if self._handler_installed:
            return

        def handler(call_ref, event, user_data):
            try:
                hkid = EventHotKeyID()
                actual_type = c_uint32(0)
                _carbon.GetEventParameter(
                    event,
                    kEventParamDirectObject,
                    typeEventHotKeyID,
                    byref(actual_type),
                    sizeof(EventHotKeyID),
                    None,
                    ctypes.cast(byref(hkid), c_void_p),
                )
                cb = self._callbacks.get(hkid.id)
                if cb:
                    cb()
            except Exception as e:
                NSLog(f"hotkey handler error: {e}")
            return noErr

        self._handler_proc = EventHandlerProc(handler)
        spec = EventTypeSpec(kEventClassKeyboard, kEventHotKeyPressed)
        target = _carbon.GetApplicationEventTarget()
        handler_out = c_void_p()
        err = _carbon.InstallEventHandler(
            target, self._handler_proc, 1, byref(spec), None, byref(handler_out)
        )
        if err != noErr:
            NSLog(f"⚠️ InstallEventHandler 失败: {err}")
            return
        self._handler_installed = True

    def register(self, modifiers, keycode, callback, label=""):
        """注册一个热键，返回 hotkey_id（失败返回 -1）"""
        if keycode < 0:
            NSLog(f"⚠️ 无效 keycode (label={label})")
            return -1

        self._install_handler()
        hk_id = self._next_id
        self._next_id += 1

        target = _carbon.GetApplicationEventTarget()
        ref = c_void_p()
        err = _carbon.RegisterEventHotKey(
            keycode, modifiers, EventHotKeyID(0x4D424152, hk_id), target, 0, byref(ref)
        )
        if err != noErr:
            NSLog(f"⚠️ RegisterEventHotKey 失败 (label={label}): {err}")
            return -1

        self._callbacks[hk_id] = callback
        self._refs[hk_id] = ref
        NSLog(f"✓ 热键已注册: {label}")
        return hk_id

    def unregister(self, hk_id):
        ref = self._refs.pop(hk_id, None)
        if ref is not None:
            _carbon.UnregisterEventHotKey(ref)
        self._callbacks.pop(hk_id, None)

    def unregister_all(self):
        for hk_id in list(self._refs.keys()):
            self.unregister(hk_id)


# 全局单例
_manager = HotkeyManager()


def get_manager():
    return _manager
