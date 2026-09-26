"""更新检查服务.

版本源优先级（fetch_update_info）：

1. **Worker 版本清单** ``GET /api/version`` —— 第一优先源。发版时由作者把
   最新版本号写进 Cloudflare KV，客户端只问这一个固定地址。
   用它是因为直接查平台 Release 列表有三个坑：Gitee/GitHub 漏同步一边就
   永远检测不到、Gitee 列表分页排序不稳、GitHub API 按 IP 限流 60 次/小时
   （机房共用出口时几个人就能打光）。
2. **Gitee Release** —— 清单不可达时降级（国内直连稳定）。
3. **GitHub Release** —— Gitee 也不可达时再降级，并回填 Gitee 下载镜像。

全部失败返回 None，调用方按"网络不可用"处理。
"""

from __future__ import annotations

import time
from datetime import datetime
from threading import Thread
from typing import Any, Callable

import requests
from PySide6.QtCore import QObject, Signal

import logging

from hnust_exam.services.config_manager import ConfigManager
from hnust_exam.utils.constants import (
    CURRENT_VERSION,
    FALLBACK_DOWNLOAD_URL,
    GITEE_OWNER,
    GITEE_UPDATE_REPO,
    GITHUB_USERNAME,
    GITHUB_REPO_NAME,
    UPDATE_MANIFEST_URL,
    UPDATE_RETRIES,
    UPDATE_TIMEOUT,
)
from hnust_exam.utils.helpers import is_semver_version, is_valid_version, version_tuple

logger = logging.getLogger(__name__)

# 保留信号引用，防止被 GC 回收后跨线程信号丢失
# 见 check_update_async 中的使用和清理逻辑
_pending_signals: list[_UpdateSignal] = []

# 版本源标识，随结果一起返回，便于用户在设置页看出"到底连的是哪个源"
SOURCE_MANIFEST = "manifest"
SOURCE_GITEE = "gitee"
SOURCE_GITHUB = "github"


class _UpdateSignal(QObject):
    """内部信号，用于将回调派发到主线程."""
    result = Signal(object)


def _http_get_json(
    url: str,
    params: dict | None = None,
    headers: dict | None = None,
    retries: int = UPDATE_RETRIES,
) -> tuple[Any, str]:
    """GET 并解析 JSON，返回 (data, error_kind).

    成功时 error_kind 为空字符串；失败时 data 为 None，error_kind 取值：
    ``timeout`` / ``rate_limit`` / ``not_found`` / ``http`` / ``network``。

    之所以要把失败原因分出来：以前所有异常都被压成 None，调用方只能显示
    "网络不可用"，限流、403、超时、解析失败看起来一模一样，根本没法排查。

    4xx 不做重试（重试也不会突然变 2xx），只对超时和网络错误退避重试。
    """
    last_error = "network"
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=UPDATE_TIMEOUT)
            if resp.status_code in (403, 429):
                # GitHub 匿名配额耗尽就是 403，重试也一样，直接返回不消耗退避时间
                logger.warning("版本源被限流(HTTP %s): %s", resp.status_code, url)
                return None, "rate_limit"
            if resp.status_code == 404:
                # 源活着但没有这条记录（例如清单还没发布过任何版本）
                return None, "not_found"
            resp.raise_for_status()
            return resp.json(), ""
        except requests.Timeout:
            last_error = "timeout"
            logger.warning("请求超时(%s/%s): %s", attempt + 1, retries + 1, url)
        except requests.HTTPError as e:
            # 4xx 已经在上面 short-circuit 过，这里剩下 5xx 之类，值得重试
            last_error = "http"
            logger.warning("HTTP 错误(%s/%s): %s - %s", attempt + 1, retries + 1, url, e)
        except requests.RequestException as e:
            last_error = "network"
            logger.warning("请求失败(%s/%s): %s - %s", attempt + 1, retries + 1, url, e)
        except ValueError as e:
            # 响应不是合法 JSON（被代理/门户拦截时常见）
            logger.warning("响应不是合法 JSON: %s - %s", url, e)
            return None, "http"
        if attempt < retries:
            time.sleep(0.8 * (2 ** attempt))  # 指数退避：0.8s, 1.6s
    return None, last_error


def _pick_exe_asset(assets: list[dict]) -> dict | None:
    """从 asset 列表里挑 Windows 安装包，只认 ``.exe``.

    不再"找不到 exe 就取 assets[0]"：实测仓库的 release 里同时挂着
    ``HNUST.exe`` 和 ``HNUST.dmg``，兜底到第一个会把 dmg 当 Windows 包下载，
    用户拿到一个装不上的文件。取不到就返回 None，上层转为"前往下载页"。
    """
    if not assets:
        return None
    return next(
        (a for a in assets if str(a.get("name", "")).lower().endswith(".exe")),
        None,
    )


def fetch_manifest_info() -> tuple[dict | None, str]:
    """从 Worker 版本清单获取发布信息.

    返回 (info, error_kind)。info 为 None 时 error_kind 说明为什么没拿到：
    ``timeout`` / ``rate_limit`` / ``http`` / ``network`` / ``bad_version``
    （清单里的版本号解析不了）/ ``empty``（清单还没发布过内容）。

    清单结构由 Worker 侧 ``/api/version`` 定义，与本函数需保持兼容::

        {"schema": 1, "version": "v1.1.9", "notes": "...",
         "published_at": "2026-09-26T12:00:00Z", "force": false,
         "assets": [{"name": "HNUST.exe", "os": "windows", "size": 123,
                     "sha256": "...", "urls": ["https://...", "https://..."]}]}
    """
    data, err = _http_get_json(UPDATE_MANIFEST_URL)
    if data is None:
        # 404 表示 Worker 活着但还没写入过发布记录：首次发版前的正常状态，
        # 记 info 而不是 warning，并让调用方据此安静降级到平台 Release。
        if err == "not_found":
            logger.info("版本清单尚未发布（404），降级到平台 Release")
            return None, "empty"
        return None, err
    if not isinstance(data, dict):
        logger.warning("版本清单格式异常（不是对象）: %r", type(data))
        return None, "http"

    latest_version = str(data.get("version", "")).strip()
    if not latest_version:
        # Worker 活着但清单体里没有版本号：多半是手工写入时写坏了
        logger.warning("版本清单为空（尚未发布任何版本）")
        return None, "empty"

    if not is_semver_version(latest_version):
        # 清单是自己写进去的结构化字段，版本号带尾巴（"v1.2.0（最新版）"）
        # 说明发布时就弄错了。这里必须报错降级，而不是猜个版本推给全体用户。
        # 旧实现更糟：它把这种值静默解析成 (1,2)，用户完全无从察觉。
        logger.error("版本清单里的版本号不是合法语义化版本: %r", latest_version)
        return None, "bad_version"

    asset = _pick_exe_asset(data.get("assets") or [])
    urls = [str(u) for u in ((asset or {}).get("urls") or []) if u]
    download_url = urls[0] if urls else ""

    published = str(data.get("published_at", "") or "")
    if published:
        try:
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            published = dt.strftime("%Y年%m月%d日 %H:%M")
        except Exception:
            pass

    return {
        "latest_ver": latest_version,
        "release_notes": str(data.get("notes", "") or "").strip() or "暂无更新日志",
        "download_url": download_url,
        "download_available": bool(download_url),
        "published_at": published,
        "expected_size": int((asset or {}).get("size") or 0),
        "release_url": str(data.get("release_url", "") or ""),
        "download_urls": urls,
        "sha256": str((asset or {}).get("sha256", "") or "").lower(),
        "force_update": bool(data.get("force", False)),
        "source": SOURCE_MANIFEST,
    }, ""


def fetch_latest_release_info(github_token: str = "") -> dict | None:
    """获取 GitHub 最新发布信息（降级源），失败返回 None.

    github_token: GitHub Personal Access Token，用于提升 API 速率限制（5000次/小时）。
    匿名调用按 **IP** 限流 60 次/小时，机房共用出口时几个人就能打光，
    所以它只作为清单源和 Gitee 都不可用时的最后兜底。
    """
    repo_api_url = (
        f"https://api.github.com/repos/{GITHUB_USERNAME}"
        f"/{GITHUB_REPO_NAME}/releases/latest"
    )
    headers = {"Authorization": f"Bearer {github_token}"} if github_token else None
    data, err = _http_get_json(repo_api_url, headers=headers)
    if not isinstance(data, dict):
        logger.warning("获取 GitHub Release 信息失败: %s", err)
        return None

    latest_version = str(data.get("tag_name", "") or "")
    if not is_valid_version(latest_version):
        logger.warning("GitHub tag 无法解析为版本号，跳过该源: %r", latest_version)
        return None

    chosen = _pick_exe_asset(data.get("assets", []) or [])
    download_url = (chosen or {}).get("browser_download_url", "")
    published = data.get("published_at", "")
    if published:
        try:
            dt = datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
            published = dt.strftime("%Y年%m月%d日 %H:%M")
        except Exception:
            pass

    return {
        "latest_ver": latest_version,
        "release_notes": (data.get("body", "") or "").strip() or "暂无更新日志",
        "download_url": download_url,
        "download_available": bool(download_url),
        "published_at": published,
        "expected_size": (chosen or {}).get("size", 0),
        "release_url": data.get("html_url", ""),
        "source": SOURCE_GITHUB,
    }


def fetch_gitee_release_info(tag_name: str) -> dict | None:
    """获取 Gitee 指定 tag 发布信息（仅用于补下载地址），失败返回 None.

    注意：不通过列表接口（排序不稳定），直接用 tag 精确查询。
    """
    repo_api_url = (
        f"https://gitee.com/api/v5/repos/{GITEE_OWNER}"
        f"/{GITEE_UPDATE_REPO}/releases/tags/{tag_name}"
    )
    release, err = _http_get_json(repo_api_url)
    if not isinstance(release, dict):
        logger.warning("获取 Gitee Release 信息失败: %s", err)
        return None

    latest_version = str(release.get("tag_name", "") or "")
    if not latest_version:
        return None

    chosen = _pick_exe_asset(release.get("assets", []) or [])
    download_url = (chosen or {}).get("browser_download_url", "")

    return {
        "latest_ver": latest_version,
        "download_url": download_url,
        "download_available": bool(download_url),
        "expected_size": (chosen or {}).get("size", 0),
        "source": SOURCE_GITEE,
    }


_GITEE_PER_PAGE = 100
_GITEE_MAX_PAGES = 5


def fetch_latest_gitee_release_info() -> dict | None:
    """从 Gitee 获取最新发布信息，失败返回 None（兼容旧调用方）."""
    info, _err = _fetch_gitee_latest_impl()
    return info


def _fetch_gitee_latest_impl() -> tuple[dict | None, str]:
    """抓取并挑出版本号最高的 Gitee release，返回 (info, error_kind).

    两个必须同时满足的点，缺一个都会表现为"发了新版但用户显示已是最新"：

    1. **遍历比较**：Gitee 列表排序不可靠，实测返回顺序是
       ``v1.1.4 … v1.0.0-beta.1, v1.1.5, v1.1.6, v1.1.7, v1.1.8``——最新的排在末尾。
    2. **必须翻页**：接口默认 ``per_page=20``，只读第一页的话，release 一超过
       20 个，新版本就落在第二页，代码永远看不见它。
    """
    repo_api_url = (
        f"https://gitee.com/api/v5/repos/{GITEE_OWNER}"
        f"/{GITEE_UPDATE_REPO}/releases"
    )
    releases: list[dict] = []
    for page in range(1, _GITEE_MAX_PAGES + 1):
        data, err = _http_get_json(
            repo_api_url,
            params={"per_page": _GITEE_PER_PAGE, "page": page},
        )
        if data is None:
            logger.warning("获取 Gitee 最新 Release 信息失败: %s", err)
            return None, err
        if not isinstance(data, list):
            logger.warning("Gitee release 列表格式异常: %r", type(data))
            return None, "http"
        releases.extend(data)
        if len(data) < _GITEE_PER_PAGE:
            break

    best = None
    best_version = None

    for release in releases:
        tag_name = release.get("tag_name", "")
        if not tag_name or not is_valid_version(tag_name):
            # 无法解析的 tag 不参与比较。旧实现会把它算成 (0,0,0)，
            # 既可能静默落选，也可能在整页都是脏数据时静默胜出。
            logger.warning("跳过无法解析的 Gitee tag: %r", tag_name)
            continue
        current = version_tuple(tag_name)
        if best_version is None or current > best_version:
            best_version = current
            best = release

    if best is None:
        return None, "empty" if not releases else "bad_version"

    latest_version = best.get("tag_name", "")

    release_notes = (best.get("body", "") or "").strip() or "暂无更新日志"

    chosen = _pick_exe_asset(best.get("assets", []) or [])
    download_url = (chosen or {}).get("browser_download_url", "")
    expected_size = (chosen or {}).get("size", 0)

    published = best.get("created_at", "")
    if published:
        try:
            # Gitee 格式: 2026-05-29T20:00:11+08:00
            # GitHub 格式: 2026-05-27T13:21:30Z
            dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
            published = dt.strftime("%Y年%m月%d日 %H:%M")
        except Exception:
            pass

    return {
        "latest_ver": latest_version,
        "release_notes": release_notes,
        "download_url": download_url,
        "download_available": bool(download_url),
        "published_at": published,
        "expected_size": expected_size,
        "release_url": best.get("html_url", ""),
        "source": SOURCE_GITEE,
    }, ""


def _is_update_needed(
    latest_version: str,
    config_manager: ConfigManager | None = None,
) -> bool:
    """检查是否确实需要更新（版本比较 + 跳过标记）.

    版本号解析不了时明确返回 False 并报 error：宁可少提示一次更新，
    也不能把脏数据当成"新版本"弹给用户，更不能像旧实现那样悄无声息。
    """
    if not is_valid_version(latest_version):
        logger.error("远程版本号无法解析，跳过更新判定: %r（本地 %s）",
                     latest_version, CURRENT_VERSION)
        return False
    if version_tuple(latest_version) <= version_tuple(CURRENT_VERSION):
        return False
    if config_manager and config_manager.load_skip_version() == latest_version:
        logger.info("用户已选择跳过版本 %s，不再提示（可在设置页恢复）", latest_version)
        return False
    return True


def _no_update_info(source: str, latest_version: str) -> dict:
    """构造"已是最新"结果.

    必须带上 source 和远程实际版本号：出问题时用户只要把设置页那行字截图发过来，
    就能立刻看出"客户端连的是哪个源、那个源上写的最新版是多少"，
    不用再靠猜去区分"真的没更新"和"某个源返回了陈旧数据"。
    """
    return {
        "no_update": True,
        "latest_ver": latest_version,
        "source": source,
        "local_version": CURRENT_VERSION,
    }


def fetch_update_info(
    config_manager: ConfigManager | None = None,
) -> dict | None:
    """同步获取更新信息，所有源都不可用时返回 None（兼容旧调用方）."""
    info, _error = fetch_update_info_with_status(config_manager)
    return info


def fetch_update_info_with_status(
    config_manager: ConfigManager | None = None,
) -> tuple[dict | None, str]:
    """带失败原因的更新检查，返回 ``(info, error)``.

    - ``info`` 不为 None → 正常结果（有更新，或 ``no_update``），``error`` 为空串
    - ``info`` 为 None → ``error`` 逐个列出每个源各自的原因，形如
      ``manifest:empty;gitee:rate_limit;github:network``

    为什么要多这个返回：以前所有失败都被压成一个 None，于是设置页里那些
    ``timeout`` / ``rate_limit`` 的错误分类分支**永远执行不到**（异常在
    ``fetch_*`` 内部就被 except 吞了，根本冒不上来），用户只能看到一句
    笼统的"网络连接失败"，你也分不清是没网、被限流还是清单没配。

    版本源优先级：Worker 清单 → Gitee Release → GitHub Release。
    """
    token = ""
    if config_manager:
        token = config_manager.load_config().get("github_token", "")

    reasons: list[str] = []

    # ── ① 首选：Worker 版本清单 ──
    info, manifest_err = fetch_manifest_info()
    if info:
        if _is_update_needed(info["latest_ver"], config_manager):
            return info, ""
        return _no_update_info(SOURCE_MANIFEST, info["latest_ver"]), ""
    reasons.append(f"manifest:{manifest_err or 'unknown'}")
    logger.info("版本清单不可用（%s），降级到平台 Release", manifest_err or "unknown")

    # ── ② 降级：Gitee Release 列表 ──
    info, gitee_err = _fetch_gitee_latest_impl()
    if info:
        if _is_update_needed(info["latest_ver"], config_manager):
            return info, ""
        return _no_update_info(SOURCE_GITEE, info["latest_ver"]), ""
    reasons.append(f"gitee:{gitee_err or 'unknown'}")

    # ── ③ 兜底：GitHub Release ──
    gh_info = fetch_latest_release_info(github_token=token)
    if not gh_info:
        reasons.append("github:unavailable")
        error = ";".join(reasons)
        logger.warning("所有版本源均不可用：%s", error)
        return None, error

    if not _is_update_needed(gh_info["latest_ver"], config_manager):
        return _no_update_info(SOURCE_GITHUB, gh_info["latest_ver"]), ""

    latest_version = gh_info["latest_ver"]

    # 尝试从 Gitee 补充下载信息
    gitee_info = fetch_gitee_release_info(latest_version)
    if (gitee_info
            and gitee_info["latest_ver"] == latest_version
            and gitee_info["download_available"]):
        gh_info["download_url"] = gitee_info["download_url"]
        gh_info["download_available"] = True
        gh_info["expected_size"] = gitee_info["expected_size"]
    else:
        gh_info["download_url"] = ""
        gh_info["download_available"] = False
        gh_info["fallback_url"] = FALLBACK_DOWNLOAD_URL

    return gh_info, ""


# 检查失败原因 → 用户可读文案
_ERROR_HINTS = {
    "timeout": "连接版本服务器超时，请稍后重试",
    "rate_limit": "版本服务器访问过于频繁（匿名请求按 IP 限流），请稍后再试",
    "bad_version": "版本源返回的版本号格式不正确，请联系作者",
    "http": "版本服务器返回了异常内容（可能被网络门户或代理拦截）",
    "network": "无法连接版本服务器，请检查网络设置",
    "unknown": "无法连接版本服务器，请检查网络设置",
    "empty": "版本清单尚未发布，且备用源也不可用",
}


def describe_check_error(error: str) -> str:
    """把 ``fetch_update_info_with_status`` 的失败原因转成人话.

    ``error`` 形如 ``manifest:empty;gitee:rate_limit;github:network``。
    挑原因时优先跳过 ``empty``——它只代表"这个源还没发布记录"，是正常降级
    路径，不是故障；真正该告诉用户的是后面那个 rate_limit 或 timeout。
    """
    if not error:
        return _ERROR_HINTS["unknown"]

    kinds = [p.partition(":")[2] for p in error.split(";") if p]
    kinds = [k for k in kinds if k]
    if not kinds:
        return _ERROR_HINTS["unknown"]

    for kind in kinds:
        if kind != "empty" and kind in _ERROR_HINTS:
            return _ERROR_HINTS[kind]
    return _ERROR_HINTS.get(kinds[0], _ERROR_HINTS["unknown"])


def check_update_async(
    callback: Callable[[dict | None], None],
    config_manager: ConfigManager | None = None,
) -> None:
    """异步检查更新，通过回调函数通知结果.

    回调通过 Qt Signal 派发到主线程执行，确保线程安全。

    注意：_pending_signals 持有信号引用防止 GC 回收后跨线程投递丢失。
    """

    sig = _UpdateSignal()
    _pending_signals.append(sig)

    def _on_signal(info: object) -> None:
        """包装回调：执行后清理信号引用，允许 GC 回收."""
        try:
            callback(info)
        finally:
            try:
                _pending_signals.remove(sig)
            except ValueError:
                pass

    sig.result.connect(_on_signal)

    def _worker() -> None:
        info = None
        try:
            info = fetch_update_info(config_manager)
        except Exception as e:
            logger.warning("更新检查线程异常: %s", e)
        finally:
            # 必须保证回调一定触发（异常时投递 None，调用方按"网络不可用"处理），
            # 否则调用方拿不到任何结果，界面会一直停在"检查中"。
            sig.result.emit(info)

    Thread(target=_worker, daemon=True).start()
