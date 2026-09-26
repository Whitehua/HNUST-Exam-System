"""无状态工具函数."""

import logging
import os
import sys
import re
import tempfile
import pandas as pd

logger = logging.getLogger(__name__)

# 版本号的每一段：允许前面是数字，后面跟任意说明文字（如 "9（修复版）"、"3-beta"）
_VERSION_NUM_RE = re.compile(r"\s*(\d+)")

# 语义化版本对齐到的段数：比较时长度必须一致，
# 否则 (1, 1) 会被 Python 判定为小于 (1, 1, 9)，把"远程有新版本"读成"远程更旧"。
_VERSION_SEGMENTS = 3


def get_resource_path(relative_path: str) -> str:
    """获取打包后的资源路径."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def get_question_bank_subdir(subdir_name: str) -> str:
    """获取题库子目录路径（委托 ResourceManager）."""
    from hnust_exam.services.resource_manager import get_question_bank_root
    return os.path.join(get_question_bank_root(), subdir_name)


def _split_version_segments(v: str) -> list[int] | None:
    """把版本字符串拆成整数段，无法解析时返回 None（绝不静默丢段）.

    解析规则：
    - 去首尾空白、去 ``v`` / ``V`` 前缀
    - 取第一个 ``-`` 之前的主版本段（``v1.2.0-beta.1`` 与 ``v1.2.0`` 视为同一版本）
    - 每个 ``.`` 分隔段取**前导数字**，因此 ``1.1.9（修复版）`` 也能读出 9
    """
    if v is None:
        return None
    s = str(v).strip().lstrip("vV").strip()
    if not s:
        return None
    main = s.split("-")[0].strip()
    if not main:
        return None
    segments: list[int] = []
    for raw in main.split("."):
        m = _VERSION_NUM_RE.match(raw)
        if not m:
            # 这一段压根没有数字：整个版本号判为无效，
            # 不能像旧实现那样把它丢掉——那会让 v1.1.9 变成 (1, 1)，
            # 比本地 (1, 1, 9) 小，从而永久判定"无需更新"。
            return None
        segments.append(int(m.group(1)))
    return segments or None


# 严格的语义化版本号：v1.2.3 / 1.2.3 / v1.2.3-beta.1
_SEMVER_RE = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def is_semver_version(v: str) -> bool:
    """校验**结构化字段**里的版本号（版本清单等）是否为干净的语义化版本.

    和 ``is_valid_version`` 的分工是刻意的：

    - ``is_valid_version`` 宽松，服务于手工创建的 Gitee/GitHub tag。
      ``v1.1.9（修复版）`` 必须读出 (1,1,9)，判废反而会丢掉真实可用的版本。
    - ``is_semver_version`` 严格，服务于自己写的清单字段。版本号带尾巴
      说明发布时就弄错了，应该报错降级，而不是猜一个版本推给全体用户。
    """
    return bool(_SEMVER_RE.match(str(v).strip())) if v is not None else False


def is_valid_version(v: str) -> bool:
    """判断版本字符串能否被可靠解析（供调用方区分"读不懂"和"真的旧"）."""
    return _split_version_segments(v) is not None


def version_tuple(v: str) -> tuple:
    """将应用版本号（语义化版本）转为可比较的定长元组.

    与 ``hnust_exam.utils.version.parse_version`` **不是一回事**：那个服务的是
    题库日期版本 ``yyyy.mm.dd.tttt``，拿它解析 ``"v1.0.0"`` 会得到 (0, 0, 0, 0)
    （test_version_comparison.py 里就锁着这条断言），所以更新检查不能用它。

    无效输入返回全 0 元组并记录 warning；调用方应先用 ``is_valid_version``
    判断，避免把"解析失败"误报成"没有新版本"。
    """
    segments = _split_version_segments(v)
    if segments is None:
        logger.warning("无法解析的版本号: %r", v)
        return (0,) * _VERSION_SEGMENTS
    # 补齐到固定长度，保证不同段数的版本号可以正确比较
    while len(segments) < _VERSION_SEGMENTS:
        segments.append(0)
    return tuple(segments)


def normalize_answer(ans: str, q_type: str) -> str:
    """标准化答案字符串用于比较.

    判断题将中文/布尔/数字形式统一映射为 a/b。
    
    Args:
        ans: 用户答案或标准答案
        q_type: 题型（"判断"、"单选"等）
        
    Returns:
        标准化后的答案字符串
    """
    # 先处理 NaN 值（pandas 读取 Excel 时可能转为 float('nan') 或 "NaN" 字符串）
    if pd.isna(ans):
        return ""
    
    ans_str = str(ans).strip().lower()
    
    # 过滤 "nan" 字符串
    if ans_str == "nan":
        return ""
    
    ans_str = re.sub(r"^【[^】]*】\s*", "", ans_str)
    
    if q_type == "判断":
        mapping = {
            "对": "a", "错": "b", "t": "a", "f": "b",
            "true": "a", "false": "b", "1": "a", "0": "b",
            "y": "a", "n": "b", "yes": "a", "no": "b",
            "正确": "a", "错误": "b", "√": "a", "×": "b",
        }
        ans_str = mapping.get(ans_str, ans_str)
    
    return ans_str


def normalize_code(code: str) -> str:
    """标准化代码：strip每行，去除空行."""
    lines = [line.strip() for line in str(code).strip().splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def normalize_code_flexible(code: str) -> str:
    """灵活标准化代码：统一换行符、去除空行、统一引号."""
    code = str(code).strip()
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in code.split("\n")]
    lines = [line for line in lines if line]
    normalized = [line.replace("'", '"') for line in lines]
    return "\n".join(normalized)


def get_log_dir() -> str:
    """获取日志目录."""
    try:
        docs = os.path.expanduser("~/Documents")
        if not os.path.isdir(docs):
            docs = os.path.expanduser("~")
        log_dir = os.path.join(docs, "HNUST_Exam_Logs")
        os.makedirs(log_dir, exist_ok=True)
        return log_dir
    except Exception:
        # 退回 exe 所在目录是不可靠的：装在 Program Files 或只读介质上时写不进去，
        # 崩溃日志会彻底丢失。临时目录一定可写。
        return tempfile.gettempdir()
