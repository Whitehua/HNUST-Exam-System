"""更新检查服务测试.

这块以前一个测试都没有，所以"发了新版但用户显示已是最新"反复出现却定位不了。
下面每个用例都对应一个真实踩过的坑，改 update_checker 时请保证它们全绿。
"""

import pytest
import requests

from hnust_exam.services import update_checker as uc
from hnust_exam.services.config_manager import ConfigManager
from hnust_exam.utils.helpers import (
    is_semver_version,
    is_valid_version,
    version_tuple,
)


# ── 版本号解析：静默丢段陷阱 ────────────────────────────────────────
# 旧实现用 `if x.isdigit()` 过滤解析不了的段，结果 tag 只要带中文说明或
# 尾部空格就会掉一位（v1.1.9 → (1,1)），比本地 (1,1,9) 小，于是永久判定
# "远程比我还旧"，更新提示再也不出现，而且日志里一个字都没有。

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("v1.1.9", (1, 1, 9)),
        ("1.1.9", (1, 1, 9)),
        ("v1.1.9（修复版）", (1, 1, 9)),
        ("v1.1.9 ", (1, 1, 9)),
        ("  v1.1.9", (1, 1, 9)),
        ("v1.1.9-beta.1", (1, 1, 9)),
        ("v1.1.9\n", (1, 1, 9)),
        ("v1.2", (1, 2, 0)),
        ("v1.10.0", (1, 10, 0)),
    ],
)
def test_version_tuple_does_not_drop_segments(raw, expected):
    assert version_tuple(raw) == expected


@pytest.mark.parametrize("bad", ["", "Release-1.1.9", "latest", None, "vv", "中文"])
def test_unparsable_version_is_flagged_not_silently_truncated(bad):
    assert is_valid_version(bad) is False
    assert version_tuple(bad) == (0, 0, 0)


def test_cross_digit_comparison_still_correct():
    """段数补齐后 v1.2.0 能正确盖过 v1.1.9（旧实现靠元组长度侥幸对）."""
    assert version_tuple("v1.2.0") > version_tuple("v1.1.9")
    assert version_tuple("v1.10.0") > version_tuple("v1.9.0")


# ── 宽松解析与严格校验的分工 ────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,strict_ok",
    [
        ("v1.2.0", True),
        ("1.2.0", True),
        ("v1.2.0-beta.1", True),
        ("v1.2.0+build.7", True),
        ("v1.2.0（最新版）", False),
        ("latest", False),
        ("v1.2", False),
        ("", False),
        (None, False),
    ],
)
def test_semver_check_is_strict(raw, strict_ok):
    assert is_semver_version(raw) is strict_ok


def test_lenient_and_strict_checks_have_different_jobs():
    """同一个字符串在两种校验下结论应当不同，这是刻意的分工，不是不一致.

    Gitee tag 是人手工建的，容忍尾巴才能拿到正确版本；
    清单字段是自己程序写进去的，带尾巴就该当场拒绝并降级。
    """
    dirty = "v1.1.9（修复版）"
    assert is_valid_version(dirty) is True
    assert version_tuple(dirty) == (1, 1, 9)
    assert is_semver_version(dirty) is False

# ── 更新判定 ────────────────────────────────────────────────────────

def test_is_update_needed_basic(monkeypatch):
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")
    assert uc._is_update_needed("v1.2.0") is True
    assert uc._is_update_needed("v1.1.9") is False
    assert uc._is_update_needed("v1.1.8") is False


def test_is_update_needed_rejects_garbage_remote(monkeypatch):
    """脏版本号不能触发更新，否则会把 "最新版" 这种字符串推给用户当新版本."""
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")
    assert uc._is_update_needed("最新版") is False
    assert uc._is_update_needed("") is False


def test_skipped_version_is_not_promoted_again(monkeypatch):
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")
    cfg = ConfigManager()          # conftest 已把 skip_ver 重定向到临时目录
    cfg.save_skip_version("v1.2.0")
    assert uc._is_update_needed("v1.2.0", cfg) is False
    assert uc._is_update_needed("v1.3.0", cfg) is True


# ── asset 挑选 ──────────────────────────────────────────────────────

def test_pick_exe_asset_never_falls_back_to_non_exe():
    """实测 release 同时挂着 HNUST.exe 和 HNUST.dmg，兜底取第一个会下到 dmg."""
    assert uc._pick_exe_asset([]) is None
    assert uc._pick_exe_asset([{"name": "HNUST.dmg"}]) is None
    picked = uc._pick_exe_asset(
        [{"name": "HNUST.dmg"}, {"name": "HNUST.exe"}]
    )
    assert picked["name"] == "HNUST.exe"


# ── 清单源 ──────────────────────────────────────────────────────────

MANIFEST_OK = {
    "schema": 1,
    "version": "v1.2.0",
    "notes": "修了一堆更新问题",
    "published_at": "2026-09-26T12:00:00Z",
    "force": False,
    "release_url": "https://github.com/x/releases/tag/v1.2.0",
    "assets": [
        {"name": "HNUST.dmg", "os": "macos", "size": 1, "sha256": "", "urls": ["https://x/dmg"]},
        {
            "name": "HNUST.exe", "os": "windows", "size": 93961064, "sha256": "ABCDEF",
            "urls": ["https://giteemirror/a.exe", "https://githubmirror/a.exe"],
        },
    ],
}

GITEE_RELEASES_V120 = [
    {
        "tag_name": "v1.2.0",
        "body": "gitee 上的说明",
        "created_at": "2026-09-26T20:00:11+08:00",
        "html_url": "https://gitee.com/x/releases/v1.2.0",
        "assets": [
            {"name": "HNUST.exe", "browser_download_url": "https://gitee/a.exe", "size": 10},
        ],
    },
]


def test_manifest_is_preferred_and_fully_parsed(monkeypatch):
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")
    calls = []

    def fake_http(url, params=None, headers=None, **kw):
        calls.append(url)
        return MANIFEST_OK, ""

    monkeypatch.setattr(uc, "_http_get_json", fake_http)

    info = uc.fetch_update_info()
    assert info["latest_ver"] == "v1.2.0"
    assert info["source"] == uc.SOURCE_MANIFEST
    assert info["download_available"] is True
    assert info["download_url"] == "https://giteemirror/a.exe"
    assert info["sha256"] == "abcdef"
    assert info["expected_size"] == 93961064
    # 清单成功时不该再去打 Gitee/GitHub（省掉两次跨境请求）
    assert len(calls) == 1


def test_no_update_result_carries_source_for_troubleshooting(monkeypatch):
    """"已是最新" 必须带上来源和远程版本，否则用户截图也看不出连的是哪个源."""
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.2.0")
    monkeypatch.setattr(uc, "_http_get_json", lambda url, **kw: (MANIFEST_OK, ""))

    info = uc.fetch_update_info()
    assert info["no_update"] is True
    assert info["latest_ver"] == "v1.2.0"
    assert info["source"] == uc.SOURCE_MANIFEST
    assert info["local_version"] == "v1.2.0"


def test_manifest_bad_version_degrades_instead_of_promoting_garbage(monkeypatch):
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")
    calls = []

    def fake_http(url, params=None, headers=None, **kw):
        calls.append(url)
        if "api/version" in url:
            return {"version": "v1.2.0（最新版）", "assets": MANIFEST_OK["assets"]}, ""
        if url.endswith("/releases"):
            return GITEE_RELEASES_V120, ""
        return None, "network"

    monkeypatch.setattr(uc, "_http_get_json", fake_http)

    info, err = uc.fetch_manifest_info()
    assert info is None and err == "bad_version"

    # 坏清单不该让软件彻底瞎掉，要能降级到 Gitee
    whole = uc.fetch_update_info()
    assert whole["source"] == uc.SOURCE_GITEE


def test_falls_back_to_gitee_when_manifest_not_published(monkeypatch):
    """Worker 还没写发布记录（404）是正常状态，必须安静降级而非报错."""
    monkeypatch.setattr(uc, "CURRENT_VERSION", "v1.1.9")

    def fake_http(url, params=None, headers=None, **kw):
        if "api/version" in url:
            return None, "not_found"
        if url.endswith("/releases"):
            return GITEE_RELEASES_V120, ""
        return None, "network"

    monkeypatch.setattr(uc, "_http_get_json", fake_http)
    info = uc.fetch_update_info()
    assert info["latest_ver"] == "v1.2.0"
    assert info["source"] == uc.SOURCE_GITEE


# ── Gitee 分页：只读第一页的回归 ────────────────────────────────────

def test_gitee_pagination_reaches_beyond_first_page(monkeypatch):
    """Gitee 默认 per_page=20 且排序不稳，最新版落在第二页时也必须找到."""
    page1 = [{"tag_name": f"v1.0.{i}"} for i in range(100)]
    page2 = GITEE_RELEASES_V120
    pages_seen = []

    def fake_http(url, params=None, headers=None, **kw):
        page = (params or {}).get("page")
        pages_seen.append(page)
        if page == 1:
            return page1, ""
        if page == 2:
            return page2, ""
        return [], ""

    monkeypatch.setattr(uc, "_http_get_json", fake_http)
    info = uc.fetch_latest_gitee_release_info()
    assert info is not None
    assert info["latest_ver"] == "v1.2.0"
    assert 2 in pages_seen, "没翻页就找不到第二页的新版本，正是原来的 bug"


def test_gitee_stops_paginating_on_partial_page(monkeypatch):
    pages_seen = []

    def fake_http(url, params=None, headers=None, **kw):
        pages_seen.append((params or {}).get("page"))
        return GITEE_RELEASES_V120, ""     # 只有 1 条，不足一页

    monkeypatch.setattr(uc, "_http_get_json", fake_http)
    uc.fetch_latest_gitee_release_info()
    assert pages_seen == [1], "最后一页不满就应该停止翻页"


def test_gitee_skips_unparsable_tags(monkeypatch):
    """脏 tag 不能参与比较，否则一个 "latest" 就能把真实版本顶掉或全军覆没."""
    releases = [
        {"tag_name": "latest"},
        {"tag_name": "Release-nightly"},
        {"tag_name": "v1.2.0", "assets": [], "body": "", "created_at": "", "html_url": ""},
    ]
    monkeypatch.setattr(uc, "_http_get_json", lambda url, **kw: (releases, ""))
    info = uc.fetch_latest_gitee_release_info()
    assert info["latest_ver"] == "v1.2.0"


def test_gitee_returns_none_when_every_tag_is_dirty(monkeypatch):
    releases = [{"tag_name": "latest"}, {"tag_name": "nightly"}]
    monkeypatch.setattr(uc, "_http_get_json", lambda url, **kw: (releases, ""))
    assert uc.fetch_latest_gitee_release_info() is None


# ── HTTP 失败分类与重试 ─────────────────────────────────────────────

def test_rate_limit_short_circuits_without_retry(monkeypatch):
    """403/429 是配额耗尽，重试只会更快烧完，必须立刻返回."""
    calls = []

    class FakeResp:
        status_code = 403

        def raise_for_status(self):
            raise AssertionError("限流后不该继续")

    monkeypatch.setattr(uc.requests, "get", lambda url, **kw: calls.append(url) or FakeResp())
    data, err = uc._http_get_json("https://api.github.com/x", retries=3)
    assert data is None
    assert err == "rate_limit"
    assert len(calls) == 1


def test_timeout_is_retried_then_reported(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        raise requests.Timeout("too slow")

    monkeypatch.setattr(uc.requests, "get", fake_get)
    monkeypatch.setattr(uc.time, "sleep", lambda s: None)   # 别真等退避时间

    data, err = uc._http_get_json("https://x", retries=2)
    assert data is None
    assert err == "timeout"
    assert len(calls) == 3      # 首次 + 2 次重试


def test_404_maps_to_not_found(monkeypatch):
    class FakeResp:
        status_code = 404

        def raise_for_status(self):
            raise AssertionError("404 应提前返回")

    monkeypatch.setattr(uc.requests, "get", lambda url, **kw: FakeResp())
    data, err = uc._http_get_json("https://x")
    assert data is None and err == "not_found"


def test_non_json_body_is_classified_as_http(monkeypatch):
    """被校园网门户/代理拦截时会返回 HTML，不能当成"没有更新"."""

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("Expecting value: line 1 column 1")

    monkeypatch.setattr(uc.requests, "get", lambda url, **kw: FakeResp())
    data, err = uc._http_get_json("https://x")
    assert data is None and err == "http"
