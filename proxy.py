"""
Meowser — 代理配置（macOS 14+）
通过 Network.framework 创建 nw_proxy_config_t，
绑定到 WKWebsiteDataStore.proxyConfigurations 强制走指定代理。
这样可以绕开系统 VPN（VPN 走系统路由，代理直接覆盖）。

API_AVAILABLE(macos(14.0)) — 旧系统会失败但不会崩。
"""

import ctypes
from ctypes import c_char_p, c_void_p, c_uint16
from Foundation import NSLog
import objc

# ── 加载 Network framework ─────────────────────
try:
    _network = ctypes.CDLL("/System/Library/Frameworks/Network.framework/Network")
except OSError:
    _network = None


def _setup_signatures():
    """设置 C 函数签名（仅当库可用）"""
    if _network is None:
        return False
    try:
        # nw_endpoint_t nw_endpoint_create_host(const char *hostname, const char *port);
        _network.nw_endpoint_create_host.argtypes = [c_char_p, c_char_p]
        _network.nw_endpoint_create_host.restype = c_void_p

        # nw_proxy_config_t nw_proxy_config_create_socksv5(nw_endpoint_t);
        _network.nw_proxy_config_create_socksv5.argtypes = [c_void_p]
        _network.nw_proxy_config_create_socksv5.restype = c_void_p

        # nw_proxy_config_t nw_proxy_config_create_http_connect(nw_endpoint_t, sec_protocol_options_t);
        _network.nw_proxy_config_create_http_connect.argtypes = [c_void_p, c_void_p]
        _network.nw_proxy_config_create_http_connect.restype = c_void_p
        return True
    except Exception as e:
        NSLog(f"proxy: signature setup failed: {e}")
        return False


_AVAILABLE = _setup_signatures()


def is_available():
    """是否能创建 nw_proxy_config（取决于 macOS 14+ 和 Network.framework）"""
    return _AVAILABLE


def make_proxy_config(proxy_type, host, port):
    """
    构造 nw_proxy_config_t
    - proxy_type: 'socks5' / 'http'
    - host: '127.0.0.1'
    - port: int
    返回 PyObjC 包裹的 NSObject (nw_proxy_config_t)，失败返回 None
    """
    if not _AVAILABLE:
        return None
    try:
        endpoint_ptr = _network.nw_endpoint_create_host(
            str(host).encode("utf-8"),
            str(port).encode("utf-8"),
        )
        if not endpoint_ptr:
            NSLog(f"proxy: nw_endpoint_create_host failed for {host}:{port}")
            return None

        if proxy_type == "socks5":
            cfg_ptr = _network.nw_proxy_config_create_socksv5(endpoint_ptr)
        elif proxy_type == "http":
            cfg_ptr = _network.nw_proxy_config_create_http_connect(endpoint_ptr, None)
        else:
            NSLog(f"proxy: unsupported type {proxy_type}")
            return None

        if not cfg_ptr:
            NSLog(f"proxy: nw_proxy_config_create_* failed")
            return None

        # 把 raw C pointer 桥接成 PyObjC 对象（nw_proxy_config_t 在 macOS 14+ 是 NSObject）
        try:
            obj = objc.objc_object(c_void_p=cfg_ptr)
        except Exception as e:
            NSLog(f"proxy: objc_object bridge failed: {e}")
            return None
        return obj
    except Exception as e:
        NSLog(f"proxy: make_proxy_config exception: {e}")
        return None


def apply_to_data_store(data_store, proxy_dict):
    """
    给 WKWebsiteDataStore 应用代理配置
    proxy_dict 形如:
        {"type": "direct"}                                       # 直连
        {"type": "socks5", "host": "127.0.0.1", "port": 1087}
        {"type": "http",   "host": "127.0.0.1", "port": 7890}
    返回 True 成功，False 失败（不抛异常）
    """
    try:
        ptype = (proxy_dict or {}).get("type", "direct")
        if ptype == "direct" or ptype == "system":
            # 直连 / 系统代理 — 不设置 proxyConfigurations 即可
            try:
                data_store.setProxyConfigurations_([])
            except Exception:
                pass
            return True

        if ptype not in ("socks5", "http"):
            NSLog(f"proxy: unknown type {ptype}, falling back to direct")
            return False

        host = proxy_dict.get("host", "127.0.0.1")
        port = int(proxy_dict.get("port", 0))
        if not host or port <= 0:
            NSLog(f"proxy: invalid host/port {host}:{port}")
            return False

        cfg = make_proxy_config(ptype, host, port)
        if cfg is None:
            return False

        try:
            data_store.setProxyConfigurations_([cfg])
            NSLog(f"✓ 代理已生效: {ptype}://{host}:{port}")
            return True
        except Exception as e:
            # macOS 13 以下不存在该方法
            NSLog(f"proxy: setProxyConfigurations_ unavailable (需 macOS 14+): {e}")
            return False
    except Exception as e:
        NSLog(f"proxy: apply_to_data_store exception: {e}")
        return False
