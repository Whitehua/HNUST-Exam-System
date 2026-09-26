"""自动更新模块：下载新版本 exe → 校验 → 替换 → 重启."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

import requests

logger = __import__("logging").getLogger(__name__)

# 下载整体重试次数。国内直连 GitHub 下 90MB 断流是常态，
# 一次断掉就整个作废的话，用户看到的就是"更新总是失败"。
DOWNLOAD_ATTEMPTS = 4
DOWNLOAD_CHUNK = 64 * 1024
# 替换脚本等待新 exe 文件锁释放的最长重试次数（每次约 1 秒）
REPLACE_TRIES = 45


def get_app_exe_path() -> str:
    """获取当前应用 exe 的真实路径.

    - frozen（PyInstaller 打包）：返回用户双击的那个原始 exe 的绝对路径
    - 开发环境：返回 Python 解释器路径
    """
    if getattr(sys, "frozen", False):
        return os.path.abspath(sys.argv[0])
    return sys.executable


def check_write_permission(path: str) -> bool:
    """检查指定路径所在目录是否可写."""
    return os.access(os.path.dirname(path), os.W_OK)


def get_temp_download_path() -> str:
    """获取临时下载路径，避免污染安装目录."""
    return os.path.join(tempfile.gettempdir(), "HNUST_update_tmp.exe")


def _cleanup_temp(path: str) -> None:
    """清理临时文件."""
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _sha256_of_file(path: str) -> str:
    """分块计算文件 sha256，避免把 90MB 一次读进内存."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_once(
    url: str,
    save_path: str,
    total_hint: int,
    progress_callback,
    should_cancel,
) -> tuple[bool, str, str, int]:
    """单次下载尝试，支持从已存在部分续传.

    Returns (ok, error_msg, kind, downloaded_total)
    kind: ``ok`` / ``resume_reset``（服务器不支持 Range，已从头重写）/
          ``retryable``（网络类，可再试）/ ``fatal``（写盘失败等，重试无意义）
    """
    resume_from = os.path.getsize(save_path) if os.path.exists(save_path) else 0
    headers = {"Range": f"bytes={resume_from}-"} if resume_from > 0 else {}

    try:
        resp = requests.get(
            url, stream=True, timeout=(15, 60), headers=headers,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        return False, f"无法连接服务器：{e}", "retryable", resume_from

    # 关键正确性判断：只有 206 才表示服务器真的接受了 Range 请求。
    # 返回 200 说明它不支持续传，此时**必须从头覆盖重写**——
    # 往已有半截文件后面追加会得到一个坏 exe，而且大小校验都可能骗过去。
    if resp.status_code == 206:
        mode = "ab"
        downloaded = resume_from
    else:
        mode = "wb"
        downloaded = 0
        resume_from = 0

    total_length = 0
    content_length = resp.headers.get("content-length")
    if content_length:
        # 206 时 content-length 是"剩余部分"长度，要加上已下载部分
        total_length = int(content_length) + downloaded
    elif total_hint > 0:
        total_length = total_hint

    start_time = time.time()
    last_emit = 0.0

    try:
        with open(save_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK):
                if should_cancel and should_cancel():
                    resp.close()
                    return False, "下载已取消", "fatal", downloaded
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)

                if progress_callback and total_length > 0 and time.time() - last_emit > 0.2:
                    last_emit = time.time()
                    percent = min(int(downloaded * 100 / total_length), 100)
                    elapsed = time.time() - start_time
                    if elapsed > 0.5 and downloaded > resume_from:
                        speed_mb = round((downloaded - resume_from) / elapsed / 1024 / 1024, 2)
                        remaining_bytes = max(total_length - downloaded, 0)
                        rate = (downloaded - resume_from) / elapsed
                        remaining = min(int(remaining_bytes / rate), 3599) if rate > 0 else 0
                    else:
                        speed_mb = 0.0
                        remaining = 0
                    progress_callback(percent, speed_mb, remaining)
    except (requests.RequestException, OSError) as e:
        # 网络中断：保留半截文件，下次尝试用 Range 续传
        resp.close()
        if isinstance(e, OSError):
            return False, f"写入文件失败：{e}", "fatal", downloaded
        return False, f"下载中断：{e}", "retryable", downloaded

    resp.close()
    if downloaded == 0:
        return False, "下载内容为空", "retryable", 0
    return True, "", "ok", downloaded


def download_file(
    url: str,
    save_path: str,
    progress_callback=None,
    expected_size: int = 0,
    expected_sha256: str = "",
    urls: list[str] | None = None,
    should_cancel=None,
) -> tuple[bool, str]:
    """下载文件到临时路径：多镜像轮换 + 断点续传 + 完整性校验.

    Args:
        url: 首选下载地址（为兼容旧调用方保留）
        save_path: 保存路径（临时目录）
        progress_callback: 回调 (percent, speed_mb, remaining_sec)
        expected_size: 预期字节数，用于大小校验
        expected_sha256: 预期 sha256（版本清单下发），用于内容校验
        urls: 全部可用镜像，按顺序轮换；为空时退化为只用 url
        should_cancel: 返回 True 时中断下载

    Returns:
        (success, error_msg)
    """
    mirrors = [u for u in (urls or []) if u] or ([url] if url else [])
    if not mirrors:
        return False, "没有可用的下载地址"

    # 换版本或换镜像时不能拿旧文件续传。先按预期大小粗筛一遍，
    # 大小对不上的残留文件直接删掉重下（单个明确的临时文件路径）。
    if expected_size > 0 and os.path.exists(save_path):
        if os.path.getsize(save_path) > expected_size:
            _cleanup_temp(save_path)

    last_err = ""
    for attempt in range(DOWNLOAD_ATTEMPTS):
        if should_cancel and should_cancel():
            _cleanup_temp(save_path)
            return False, "下载已取消"

        target = mirrors[attempt % len(mirrors)]
        ok, err, kind, _got = _download_once(
            target, save_path, expected_size, progress_callback, should_cancel,
        )

        if kind == "fatal":
            _cleanup_temp(save_path)
            return False, err

        if not ok:
            last_err = err
            logger.warning("下载第 %s/%s 次失败（%s）: %s",
                           attempt + 1, DOWNLOAD_ATTEMPTS, target[:40], err)
            time.sleep(min(1.5 * (attempt + 1), 5))
            continue

        # ── 大小校验 ──
        actual_size = os.path.getsize(save_path)
        if expected_size > 0 and actual_size != expected_size:
            last_err = f"文件大小不匹配（预期 {expected_size}，实际 {actual_size}）"
            logger.warning("%s，准备重下", last_err)
            _cleanup_temp(save_path)   # 坏文件不能留着续传
            continue

        # ── 内容校验：大小相同但内容不同（截断/串位）也能抓住 ──
        if expected_sha256:
            try:
                actual = _sha256_of_file(save_path)
            except OSError as e:
                _cleanup_temp(save_path)
                return False, f"无法读取下载结果：{e}"
            if actual != expected_sha256.lower():
                last_err = "文件校验失败（sha256 不匹配），下载结果可能被篡改或不完整"
                logger.warning("%s：期望 %s 实际 %s", last_err, expected_sha256, actual)
                _cleanup_temp(save_path)
                continue

        return True, ""

    _cleanup_temp(save_path)
    return False, last_err or "下载失败"



def get_temp_replace_script_path() -> str:
    """外部替换脚本的路径（放临时目录，不污染安装目录）."""
    return os.path.join(tempfile.gettempdir(), "HNUST_update_replace.cmd")


_REPLACE_SCRIPT = """@echo off
setlocal enableextensions
set "NEW_PATH={new}"
set "TARGET_PATH={target}"
set "BACKUP_PATH={backup}"
set /a TRIES=0
:try_move
move /Y "%NEW_PATH%" "%TARGET_PATH%" >nul 2>&1
if not errorlevel 1 goto launched
set /a TRIES+=1
if %TRIES% geq {tries} goto rollback
ping -n 2 127.0.0.1 >nul
goto try_move
:rollback
move /Y "%BACKUP_PATH%" "%TARGET_PATH%" >nul 2>&1
start "" "%TARGET_PATH%"
goto finish
:launched
start "" "%TARGET_PATH%"
:finish
del "%~f0" >nul 2>&1
"""


def _build_replace_script(new_exe: str, target_exe: str, backup_exe: str) -> str:
    """生成"重试替换 → 启动新版本 / 失败回滚"的批处理内容.

    为什么不在本进程里直接 ``shutil.move``：新下载的 exe 刚落盘就会被
    Defender 实时保护抓住扫描并短暂独占，此刻 move 概率性抛
    ``PermissionError``——这正是"有时能更新、有时提示替换失败"的来源。
    交给外部脚本后，脚本既等得到本进程彻底退出，也能在锁冲突时反复重试。

    路径统一走 ``set "VAR=值"`` 形式，这样含空格甚至 ``&`` 的路径都不会
    被 cmd 解释成命令分隔符。
    """
    return _REPLACE_SCRIPT.format(
        new=new_exe, target=target_exe, backup=backup_exe, tries=REPLACE_TRIES,
    )


def _spawn_detached(script_path: str) -> None:
    """分离启动一个脚本：不随本进程退出而被带走，也不占控制台."""
    DETACHED_PROCESS = 0x00000008
    flags = DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        flags |= subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        ["cmd.exe", "/c", script_path],
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def replace_and_restart(new_exe_path: str) -> tuple[bool, str]:
    """用新版本替换当前 exe 并重启（仅 frozen 环境）.

    流程：
    1. 本进程内把当前 exe 改名让位（Windows 允许重命名正在运行的 exe）
    2. 启动外部脚本，由它重试把新 exe 放到原位、成功后启动、失败则回滚
    3. 本进程退出，交出文件句柄

    Returns:
        (success, error_msg) —— 成功路径不会返回（进程已 exit）
    """
    if not getattr(sys, "frozen", False):
        return False, "非打包环境，无法自动替换"

    exe_path = get_app_exe_path()
    backup_path = exe_path + ".old.bak"

    if not check_write_permission(exe_path):
        return False, "权限不足，请以管理员身份运行或将程序移至非系统目录"

    # 步骤1：让位。这一步必须在本进程里做——重命名正在运行的 exe 是允许的，
    # 而且只有目标路径空出来，新文件才放得进去。
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.replace(exe_path, backup_path)
    except OSError as e:
        return False, f"无法备份当前版本：{e}"

    # 步骤2：交棒给外部脚本
    if os.name != "nt":
        # 非 Windows 没有杀软锁文件的问题，也跑不了 .cmd，直接移动。
        # 这条分支基本不会在正式发行版里走到，保留是为了不在开发环境里炸。
        try:
            shutil.move(new_exe_path, exe_path)
        except OSError as e:
            try:
                os.replace(backup_path, exe_path)
            except OSError:
                pass
            return False, f"替换文件失败：{e}"
        subprocess.Popen([exe_path], close_fds=True)
        sys.exit(0)

    script_path = get_temp_replace_script_path()
    try:
        with open(script_path, "w", encoding="gbk") as f:
            f.write(_build_replace_script(new_exe_path, exe_path, backup_path))
    except OSError as e:
        _restore_backup(backup_path, exe_path)
        return False, f"无法写入更新脚本：{e}"

    try:
        _spawn_detached(script_path)
    except OSError as e:
        _restore_backup(backup_path, exe_path)
        _cleanup_temp(script_path)
        return False, f"无法启动更新脚本（可能被杀毒软件拦截）：{e}"

    sys.exit(0)


def _restore_backup(backup_path: str, exe_path: str) -> None:
    """交棒失败时把旧版本放回原位，保证程序还能启动."""
    try:
        os.replace(backup_path, exe_path)
    except OSError:
        logger.error("回滚失败，旧版本仍在 %s", backup_path)


def clean_old_backup() -> None:
    """启动时清理上次更新留下的 .old.bak 残留文件."""
    if not getattr(sys, "frozen", False):
        return
    exe_path = get_app_exe_path()
    backup_path = exe_path + ".old.bak"
    if os.path.exists(backup_path):
        try:
            os.remove(backup_path)
        except OSError:
            pass
