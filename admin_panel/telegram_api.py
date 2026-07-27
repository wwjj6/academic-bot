# -*- coding: utf-8 -*-
"""
اتصال مباشر بواجهة Telegram Bot API عبر urllib (بدون تبعيات خارجية).
يُستخدم من لوحة التحكم للتحقق من التوكن وإرسال الإشعارات الجماعية.
"""
import json
import urllib.request
import urllib.parse
import urllib.error

_API = "https://api.telegram.org/bot{token}/{method}"


def _call(token, method, params=None, timeout=20):
    url = _API.format(token=token, method=method)
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"ok": False, "description": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "description": str(e)}


def get_me(token):
    """التحقق من صحة التوكن — يُرجع معلومات البوت عند النجاح."""
    return _call(token, "getMe")


def send_message(token, chat_id, text):
    """إرسال رسالة إلى مستخدم واحد."""
    return _call(token, "sendMessage", {"chat_id": chat_id, "text": text})
