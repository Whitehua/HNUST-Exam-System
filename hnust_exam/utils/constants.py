"""全局常量定义."""

import os
import re


CURRENT_VERSION = "v1.1.9"
GITHUB_USERNAME = "RyanTanC"
GITHUB_REPO_NAME = "HNUST-Exam-System"

# 题库热更新（独立 Gitee 仓库）
GITEE_USERNAME = "ryan-tanc"
GITEE_REPO_NAME = "hnust-computer-exam-tiku"

# 更新检查与下载（GitHub 查版本，Gitee 下载 exe）
GITEE_OWNER = "ryan-tanc"
GITEE_UPDATE_REPO = "hnust-exam-system"
FALLBACK_DOWNLOAD_URL = "https://ryantanc.github.io/HNUST-Exam-System/download.html"

_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".hnust_exam")
CONFIG_FILE = os.path.join(_CONFIG_DIR, "config.json")
PROGRESS_FILE = os.path.join(_CONFIG_DIR, "progress.json")
SKIP_VERSION_FILE = os.path.join(_CONFIG_DIR, "skip_ver")
TELEMETRY_QUEUE_FILE = os.path.join(_CONFIG_DIR, "telemetry_queue.json")

# 用户本地题库缓存目录（持久化，断网可用）
QUESTION_BANK_DIR = os.path.join(_CONFIG_DIR, "question_bank")
QUESTION_BANK_FILES_DIR = os.path.join(QUESTION_BANK_DIR, "files")
MANIFEST_FILE = os.path.join(QUESTION_BANK_DIR, "manifest.json")

LOG_DIR = os.path.join(_CONFIG_DIR, "logs")

QUESTION_TYPE_ORDER = ["单选", "多选", "填空", "判断", "程序填空", "程序改错", "程序设计"]
PROGRAM_TYPES = {"程序设计", "程序填空", "程序改错"}

EXAM_TIME_SECONDS = 60 * 60

# 图片目录（相对于项目根目录）
IMAGES_DIR = "题库/试题图片"

REQUIRED_COLUMNS = {"题号", "题型", "题目", "正确答案", "分值"}

# 可选列（向后兼容：不存在时使用默认值）
OPTIONAL_COLUMNS = {
    "CompileCheck", "OutputCheck", "KeywordCheck", "Keywords", "ExpectedOutput", "PartialCredit",
    "编译检查", "输出检查", "关键字检查", "关键字", "预期输出", "部分得分",
}

# 匿名使用统计 Worker 地址
TELEMETRY_BASE_URL = "https://hnust-exam-telemetry.hnust-exam-stats.workers.dev"

# ── 更新检测 ────────────────────────────────────────────────
# 版本清单地址（第一优先源）：发布新版本时由作者写入 Worker KV。
# 用它而不是直接查 Gitee/GitHub Release 列表，是为了避开三个坑：
# 两个平台漏同步、Gitee 列表分页/排序不稳、GitHub API 按 IP 限流。
UPDATE_MANIFEST_URL = TELEMETRY_BASE_URL.rstrip("/") + "/api/version"

# GitHub API 匿名调用按 IP 计数（60 次/小时），机房共用出口时很容易打光；
# Gitee 同理。超时给足一点，并用 (connect, read) 元组分别控制。
UPDATE_TIMEOUT = (6, 12)
UPDATE_RETRIES = 2

# 版本号格式校验（题库热更新用）
# 合法格式：YYYY.MM.DD.HHMM（如 2026.06.01.1823）
# 非法格式：2026.06.0.1703（月/日为 0）
QUESTION_BANK_VERSION_PATTERN = re.compile(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$")
