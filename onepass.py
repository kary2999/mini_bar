"""
Meowser — 1Password CLI 集成
- 检查 op CLI 是否安装
- 列出 vault 内 items（仅 logins）
- 取出 username + password
- 注入到当前 webview 的输入框
"""

import json
import shutil
import subprocess


def is_available():
    return shutil.which("op") is not None


def is_signed_in():
    """检查是否已登录（op vault list 不报错就算）"""
    if not is_available():
        return False
    try:
        r = subprocess.run(["op", "vault", "list", "--format=json"],
                           capture_output=True, text=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


def list_logins():
    """列出所有 login 类型的 items: [(name, id, url), ...]"""
    if not is_signed_in():
        return []
    try:
        r = subprocess.run(["op", "item", "list",
                            "--categories=Login", "--format=json"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return []
        items = json.loads(r.stdout) or []
        out = []
        for it in items:
            name = it.get("title", "(未命名)")
            iid = it.get("id", "")
            urls = it.get("urls", []) or []
            url = urls[0].get("href") if urls else ""
            out.append((name, iid, url))
        return out
    except Exception:
        return []


def get_credentials(item_id):
    """取出指定 item 的 username + password。返回 (user, pwd) 或 None"""
    if not is_signed_in() or not item_id:
        return None
    try:
        r = subprocess.run(["op", "item", "get", item_id, "--format=json"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return None
        item = json.loads(r.stdout)
        user = ""
        pwd = ""
        for f in item.get("fields", []) or []:
            t = (f.get("type") or "").upper()
            label = (f.get("label") or "").lower()
            if t == "STRING" and ("user" in label or label == "username"):
                user = f.get("value", "") or ""
            elif t == "CONCEALED" or label == "password":
                pwd = f.get("value", "") or pwd
        return (user, pwd) if (user or pwd) else None
    except Exception:
        return None


def fill_js(user, pwd):
    """生成往当前页面 input 框填充 user/pwd 的 JavaScript"""
    # 转义引号
    user_e = (user or "").replace("\\", "\\\\").replace("'", "\\'")
    pwd_e  = (pwd or "").replace("\\", "\\\\").replace("'", "\\'")
    return f"""
    (function() {{
      var fired = 0;
      function trigger(el, val) {{
        try {{
          var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(el, val);
          el.dispatchEvent(new Event('input', {{ bubbles: true }}));
          el.dispatchEvent(new Event('change', {{ bubbles: true }}));
          fired++;
        }} catch(e) {{}}
      }}
      // 用户名
      var userVal = '{user_e}';
      var pwdVal = '{pwd_e}';
      if (userVal) {{
        var u = document.querySelector('input[type="email"]')
             || document.querySelector('input[type="text"][autocomplete*="username"]')
             || document.querySelector('input[type="text"][name*="user" i]')
             || document.querySelector('input[type="text"][id*="user" i]')
             || document.querySelector('input[type="text"]');
        if (u) trigger(u, userVal);
      }}
      if (pwdVal) {{
        var p = document.querySelector('input[type="password"]');
        if (p) trigger(p, pwdVal);
      }}
      return fired;
    }})();
    """
