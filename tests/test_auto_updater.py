"""下载与自更新替换测试.

对应两个过去反复出现的现象：
"下到一半就前功尽弃"（无重试无续传）和
"有时能更新有时提示替换失败"（在进程内 move 被杀软锁定的新文件）。
"""

import hashlib

import pytest
import requests

from hnust_exam.services import auto_updater as au


class _FakeResp:
    """最小可用的流式响应替身."""

    def __init__(self, payload: bytes, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.headers = {"content-length": str(len(payload))}
        self.closed = False

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int = 1):
        for i in range(0, len(self._payload), chunk_size):
            yield self._payload[i:i + chunk_size]

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """重试退避不真等."""
    monkeypatch.setattr(au.time, "sleep", lambda s: None)


# ── 断点续传 ────────────────────────────────────────────────────────

def test_resume_appends_only_when_server_returns_206(tmp_path, monkeypatch):
    save = tmp_path / "update.exe"
    save.write_bytes(b"AAAA")
    captured = {}

    def fake_get(url, **kw):
        captured.update(kw.get("headers") or {})
        return _FakeResp(b"BBBB", status=206)

    monkeypatch.setattr(au.requests, "get", fake_get)
    ok, err = au.download_file("http://x/update.exe", str(save), expected_size=8)

    assert ok, err
    assert save.read_bytes() == b"AAAABBBB"
    assert captured["Range"] == "bytes=4-"


def test_server_without_range_support_restarts_from_scratch(tmp_path, monkeypatch):
    """服务器忽略 Range 直接回全量（200）时**必须覆盖重写**.

    往已有半截文件后面追加会得到一个坏 exe，而大小校验还可能恰好被骗过去
    ——这是续传实现里最容易写错、后果又最严重的一处。
    """
    full = b"AAAABBBB"
    save = tmp_path / "update.exe"
    save.write_bytes(b"AAAA")

    monkeypatch.setattr(au.requests, "get", lambda url, **kw: _FakeResp(full, status=200))
    ok, err = au.download_file("http://x/update.exe", str(save), expected_size=len(full))

    assert ok, err
    assert save.read_bytes() == full


def test_resume_from_empty_or_missing_file_sends_no_range(tmp_path, monkeypatch):
    captured = {}
    save = tmp_path / "update.exe"

    def fake_get(url, **kw):
        captured.update(kw.get("headers") or {})
        return _FakeResp(b"DATA", status=200)

    monkeypatch.setattr(au.requests, "get", fake_get)
    ok, _ = au.download_file("http://x", str(save), expected_size=4)
    assert ok
    assert "Range" not in captured


def test_progress_percentage_counts_resumed_bytes(tmp_path, monkeypatch):
    """206 的 content-length 只是剩余长度，进度必须加回已下载部分.

    否则续传时 total_length 被算成一半，进度条瞬间跳到 100% 却还在下载。
    """
    save = tmp_path / "update.exe"
    save.write_bytes(b"A" * 50)
    percents = []

    monkeypatch.setattr(
        au.requests, "get", lambda url, **kw: _FakeResp(b"B" * 50, status=206),
    )
    ok, err = au.download_file(
        "http://x", str(save),
        progress_callback=lambda p, s, r: percents.append(p),
        expected_size=100,
    )
    assert ok, err
    assert percents and percents[-1] == 100
    assert save.stat().st_size == 100


# ── 完整性校验 ──────────────────────────────────────────────────────

def test_sha256_mismatch_is_rejected_even_when_size_matches(tmp_path, monkeypatch):
    """大小相同但内容不同（截断/串位/被篡改）时，旧实现会放过去."""
    payload = b"X" * 100
    expected = hashlib.sha256(payload).hexdigest()
    save = tmp_path / "update.exe"

    monkeypatch.setattr(
        au.requests, "get", lambda url, **kw: _FakeResp(b"Y" * 100, status=200),
    )
    ok, err = au.download_file(
        "http://x", str(save), expected_size=100, expected_sha256=expected,
    )

    assert ok is False
    assert "sha256" in err
    # 坏文件必须删掉，否则下一次"续传"会把它接着拼下去
    assert not save.exists()


def test_sha256_match_succeeds(tmp_path, monkeypatch):
    payload = b"good exe bytes"
    save = tmp_path / "update.exe"

    monkeypatch.setattr(au.requests, "get", lambda url, **kw: _FakeResp(payload, status=200))
    ok, err = au.download_file(
        "http://x", str(save),
        expected_size=len(payload),
        expected_sha256=hashlib.sha256(payload).hexdigest().upper(),   # 大小写应无关
    )
    assert ok, err
    assert save.read_bytes() == payload


def test_size_mismatch_clears_partial_file(tmp_path, monkeypatch):
    save = tmp_path / "update.exe"
    monkeypatch.setattr(au.requests, "get", lambda url, **kw: _FakeResp(b"short", status=200))
    ok, err = au.download_file("http://x", str(save), expected_size=999)
    assert ok is False
    assert "大小" in err or "不匹配" in err
    assert not save.exists()


# ── 重试与多镜像 ────────────────────────────────────────────────────

def test_falls_back_to_next_mirror_after_network_error(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        if "bad" in url:
            raise requests.ConnectionError("connection reset")
        return _FakeResp(b"DATA", status=200)

    monkeypatch.setattr(au.requests, "get", fake_get)
    ok, err = au.download_file(
        "https://m1/bad.exe", str(tmp_path / "u.exe"),
        expected_size=4,
        urls=["https://m1/bad.exe", "https://m2/good.exe"],
    )
    assert ok, err
    assert "https://m2/good.exe" in calls


def test_retries_same_url_after_transient_failure(tmp_path, monkeypatch):
    """只给一个地址时也要能重试：国内直连 GitHub 断流是常态，
    一次失败就作废等于把"更新总是失败"写死在代码里."""
    attempts = []

    def fake_get(url, **kw):
        attempts.append(1)
        if len(attempts) < 3:
            raise requests.Timeout("read timed out")
        return _FakeResp(b"DATA", status=200)

    monkeypatch.setattr(au.requests, "get", fake_get)
    ok, err = au.download_file("http://x", str(tmp_path / "u.exe"), expected_size=4)
    assert ok, err
    assert len(attempts) == 3


def test_gives_up_after_max_attempts(tmp_path, monkeypatch):
    def fake_get(url, **kw):
        raise requests.ConnectionError("no route")

    monkeypatch.setattr(au.requests, "get", fake_get)
    ok, err = au.download_file("http://x", str(tmp_path / "u.exe"), expected_size=4)
    assert ok is False
    assert err


def test_cancel_stops_before_writing(tmp_path, monkeypatch):
    save = tmp_path / "u.exe"
    monkeypatch.setattr(au.requests, "get", lambda url, **kw: _FakeResp(b"DATA"))
    ok, err = au.download_file(
        "http://x", str(save), expected_size=4, should_cancel=lambda: True,
    )
    assert ok is False
    assert "取消" in err


def test_no_url_at_all_fails_cleanly(tmp_path):
    ok, err = au.download_file("", str(tmp_path / "u.exe"))
    assert ok is False
    assert "下载地址" in err


# ── 外部替换脚本 ────────────────────────────────────────────────────

def test_replace_script_retries_then_rolls_back_then_self_deletes():
    s = au._build_replace_script(
        r"C:\temp\new.exe", r"D:\app\HNUST仿真平台.exe", r"D:\app\HNUST仿真平台.exe.old.bak",
    )
    assert ":try_move" in s and "move /Y" in s
    assert f"if %TRIES% geq {au.REPLACE_TRIES} goto rollback" in s
    # 替换一直失败要把旧版本放回去，否则程序直接启动不了
    assert ':rollback' in s
    assert 'move /Y "%BACKUP_PATH%" "%TARGET_PATH%"' in s
    assert 'start "" "%TARGET_PATH%"' in s
    assert 'del "%~f0"' in s                      # 用完自删，不在临时目录留垃圾
    assert "ping -n 2 127.0.0.1" in s             # 用 ping 而不是 timeout 延时


def test_replace_script_quotes_paths_with_spaces_and_ampersand():
    """路径里有空格或 & 时不能破坏脚本语义."""
    s = au._build_replace_script(
        r"C:\Program Files\a & b\new.exe",
        r"C:\Program Files\a & b\app.exe",
        r"C:\Program Files\a & b\app.exe.old.bak",
    )
    assert r'set "NEW_PATH=C:\Program Files\a & b\new.exe"' in s
    assert r'set "TARGET_PATH=C:\Program Files\a & b\app.exe"' in s


def test_replace_and_restart_refuses_in_dev_mode():
    """开发环境（非 frozen）绝不能真的去替换 sys.executable."""
    ok, err = au.replace_and_restart("whatever.exe")
    assert ok is False
    assert "非打包环境" in err


# ── 错误原因文案 ────────────────────────────────────────────────────

def test_empty_reason_does_not_mask_real_failure(monkeypatch):
    from hnust_exam.services import update_checker as uc

    # 清单"还没发布"是正常降级路径，不该盖住真正的故障原因
    msg = uc.describe_check_error("manifest:empty;gitee:rate_limit;github:network")
    assert "频繁" in msg

    assert "超时" in uc.describe_check_error("manifest:timeout;gitee:timeout")
    assert "尚未发布" in uc.describe_check_error("manifest:empty;gitee:empty")
    assert uc.describe_check_error("")          # 空原因也要给出话


def test_fetch_update_info_wrapper_keeps_old_contract(monkeypatch):
    """旧签名必须继续返回 dict | None，app.py 依赖这个语义."""
    from hnust_exam.services import update_checker as uc

    monkeypatch.setattr(
        uc, "fetch_update_info_with_status",
        lambda cfg=None: ({"latest_ver": "v9.9.9"}, "ignored"),
    )
    assert uc.fetch_update_info() == {"latest_ver": "v9.9.9"}
