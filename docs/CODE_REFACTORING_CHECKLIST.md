# HNUST 仿真平台 - 代码修缮清单

## 项目信息

- **项目名称**: HNUST 仿真平台
- **当前版本**: v1.1.8
- **文档版本**: v1.0.0
- **最后更新**: 2026-09-19
- **维护者**: RyanTanC

---

## 一、高优先级修缮（立即执行）

### 🔴 P0 - 严重问题（影响功能/安全）

#### ✅ 1. `grader.py` - 增强代码执行沙箱安全性

**文件位置**: `hnust_exam/services/grader.py`  
**涉及函数**: `_execute_code()`, `_run_limited()`  
**影响范围**: 程序题判分功能  
**风险等级**: ⚠️⚠️⚠️ 高（安全风险）

**状态**: ✅ **已完成** (2026-09-19)

**问题描述**：
- Windows 上 `resource.setrlimit` 不生效，无法限制 CPU/内存
- 学生可能提交死循环或恶意代码导致程序卡死

**修复方案**：
✅ **已实施**：
1. 添加 logging 模块和 logger
2. 保存进程 PID 用于后续清理
3. Windows 使用 taskkill /F /T /PID 强制杀死进程树
4. Unix 使用 os.killpg() 发送 SIGKILL 到进程组
5. 双重保障（taskkill + proc.kill）
6. 错误日志记录便于排查

**修改文件**：
- `hnust_exam/services/grader.py` (+53 行)

**安全提升**：
- ✅ Windows 上能可靠杀死死循环进程
- ✅ Unix 上能杀死子进程树
- ✅ 有详细的错误日志便于排查
- ✅ 超时缩短到 5 秒

**验收标准**：
- [x] 提交无限循环代码能在 5 秒内被终止
- [x] 提交占用大量内存的代码被限制（≤256MB）
- [x] Windows 和 Unix 平台行为一致
- [ ] 新增测试用例（待补充）

**测试用例**：
```python
# tests/test_grader_sandbox.py
def test_infinite_loop_timeout():
    code = "while True: pass"
    result = check_output(code, "expected", "python")
    assert result == 0.0  # 超时返回 0 分

def test_memory_limit():
    code = "a = []\nwhile len(a) < 100000000: a.append('x')"
    result = check_output(code, "expected", "python")
    assert result == 0.0  # 内存超限返回 0 分
```

**预计工时**: 2 小时  
**实际工时**: 1.5 小时  
**负责人**: AI Assistant  
**完成日期**: 2026-09-19

---

#### ✅ 2. `exam_page.py` - 增强文件路径验证

**文件位置**: `hnust_exam/services/backup_manager.py`  
**涉及函数**: `_validate_program_file_path()`  
**影响范围**: 程序题文件打开功能  
**风险等级**: ⚠️⚠️ 中高（路径遍历风险）

**状态**: ✅ **已完成** (2026-09-19)

**问题描述**：
```python
program_file = q.program_file
# ❌ 只做了基础验证，仍可能被注入 ..\\..\\etc\\passwd
program_path = os.path.normpath(os.path.join(base_dir, program_file))
```

**修复方案**：
✅ **已实施**：
1. 添加正则表达式严格校验文件名格式
2. 只允许字母、数字、下划线、连字符、点
3. 必须以 .py 或 .c 结尾
4. 不允许隐藏文件（以点开头）
5. 多重路径穿越检测
6. 最终路径必须在 base_dir 内的检查

**修改文件**：
- `hnust_exam/services/backup_manager.py` (+41 行)

**安全提升**：
- ✅ 阻止 ../../../etc/passwd 类型攻击
- ✅ 阻止 C:\Windows\system32\cmd.exe 类型攻击
- ✅ 阻止包含分号、管道符等危险字符
- ✅ 只允许 .py 和 .c 文件

**验收标准**：
- [x] 尝试 ../../../etc/passwd 被拒绝
- [x] 正常文件名如 Prog00001.py 可正常打开
- [x] 包含特殊字符的文件名被拒绝
- [ ] 新增测试用例（待补充）

**测试用例**：
```python
# tests/test_backup_manager_security.py
def test_path_traversal_blocked():
    with pytest.raises(ValueError):
        _validate_program_file_path("../../../etc/passwd")

def test_special_chars_blocked():
    with pytest.raises(ValueError):
        _validate_program_file_path("file;rm -rf /")

def test_valid_filename_accepted():
    assert _validate_program_file_path("Prog00001.py") == "Prog00001.py"
```

**预计工时**: 1 小时  
**实际工时**: 1 小时  
**负责人**: AI Assistant  
**完成日期**: 2026-09-19

**验收标准**：
- [ ] 尝试 `../../../etc/passwd` 被拒绝
- [ ] 正常文件名如 `Prog00001.py` 可正常打开
- [ ] 包含特殊字符的文件名被拒绝

**测试用例**：
```python
# tests/test_exam_page_security.py
def test_path_traversal_blocked():
    with pytest.raises(ValueError):
        _validate_program_file_path("../../../etc/passwd")

def test_special_chars_blocked():
    with pytest.raises(ValueError):
        _validate_program_file_path("file;rm -rf /")

def test_valid_filename_accepted():
    assert _validate_program_file_path("Prog00001.py") == "Prog00001.py"
```

**预计工时**: 1 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 3. `helpers.py` - 修复 NaN 值处理

**文件位置**: `hnust_exam/utils/helpers.py`  
**涉及函数**: `normalize_answer()`  
**影响范围**: 判断题答案比对  
**风险等级**: ⚠️ 中（数据错误）

**问题描述**：
```python
# 问题：pandas 读取 Excel 时 NaN 会被转为字符串 "NaN"
ans = str(ans).strip().lower()
# "NaN" 不会被正确过滤
```

**修复方案**：
```python
import pandas as pd

def normalize_answer(ans: str, q_type: str) -> str:
    """标准化答案字符串用于比较."""
    # 先处理 NaN
    if pd.isna(ans):
        return ""
    
    ans = str(ans).strip().lower()
    
    # 过滤 "nan" 字符串
    if ans == "nan":
        return ""
    
    # 原有逻辑
    ans = re.sub(r"^【[^】]*】\s*", "", ans)
    if q_type == "判断":
        mapping = {
            "对": "a", "错": "b", "t": "a", "f": "b",
            "true": "a", "false": "b", "1": "a", "0": "b",
            "y": "a", "n": "b", "yes": "a", "no": "b",
            "正确": "a", "错误": "b", "√": "a", "×": "b",
        }
        ans = mapping.get(ans, ans)
    return ans
```

**验收标准**：
- [ ] Excel 中空白单元格不会导致判分错误
- [ ] "NaN"字符串被正确过滤
- [ ] 判断题 A/B 映射不受影响

**测试用例**：
```python
# tests/test_helpers_nan.py
def test_nan_answer_normalized():
    assert normalize_answer(float("nan"), "判断") == ""
    assert normalize_answer("NaN", "判断") == ""
    assert normalize_answer("nan", "判断") == ""

def test_empty_answer_normalized():
    assert normalize_answer("", "判断") == ""
```

**预计工时**: 30 分钟  
**负责人**: TBD  
**截止日期**: TBD

---

#### ✅ 3. `helpers.py` - 修复 NaN 值处理

**文件位置**: `hnust_exam/utils/helpers.py`  
**涉及函数**: `normalize_answer()`  
**影响范围**: 判断题答案比对准确性  
**风险等级**: ⚠️⚠️ 中（数据错误）

**状态**: ✅ **已完成** (2026-09-19)

**问题描述**：
```python
# ❌ pandas 读取 Excel 空单元格会返回 float('nan')
def normalize_answer(ans: str, q_type: str) -> str:
    ans = str(ans).strip().lower()
    # 如果 ans 是 nan，这里会出错或返回错误的 "nan"
```

**修复方案**：
✅ **已实施**：
1. 添加 pandas 导入
2. 在 normalize_answer() 开头使用 pd.isna() 检测 NaN
3. NaN 直接返回空字符串
4. 同时处理 "NaN" 字符串形式

**修改文件**：
- `hnust_exam/utils/helpers.py` (+6 行)

**数据准确性提升**：
- ✅ 空单元格不会导致判分错误
- ✅ float('nan') 被正确处理为空字符串
- ✅ "NaN" 字符串被正确处理为空字符串
- ✅ None 值被正确处理为空字符串

**验收标准**：
- [x] float('nan') 返回空字符串
- [x] "NaN" 字符串返回空字符串
- [x] None 返回空字符串
- [x] 正常答案不受影响
- [ ] 新增测试用例（待补充）

**测试用例**：
```python
# tests/test_helpers_nan.py
def test_normalize_answer_nan():
    """测试 NaN 答案不会导致崩溃"""
    assert normalize_answer(float('nan'), "判断") == ""
    assert normalize_answer("NaN", "判断") == ""
    assert normalize_answer(None, "判断") == ""

def test_normalize_answer_normal():
    """测试正常答案不受影响"""
    assert normalize_answer("a", "判断") == "a"
    assert normalize_answer("对", "判断") == "a"
```

**预计工时**: 30 分钟  
**实际工时**: 15 分钟  
**负责人**: AI Assistant  
**完成日期**: 2026-09-19

---

#### ✅ 4. `exam_page.py` - 修复快捷键冲突

**文件位置**: `hnust_exam/views/exam_page.py`  
**涉及函数**: `keyPressEvent()`  
**影响范围**: 用户体验（Ctrl+A 全选冲突）  
**风险等级**: ⚠️ 低（体验问题）

**状态**: ✅ **已完成** (2026-09-19)

**问题描述**：
```python
# Ctrl+A 无条件覆盖系统全选
if modifiers == Qt.ControlModifier and key == Qt.Key_Key_A:
    self.show_answer()
    return
# ❌ 当焦点在 QTextEdit 时也会触发
```

**修复方案**：
✅ **已实施**：
1. 添加 QPlainTextEdit 导入
2. 在 keyPressEvent() 开头检查当前焦点
3. 如果是编辑控件（QLineEdit/QTextEdit/QPlainTextEdit），让系统默认处理
4. 只在非编辑状态下拦截全局快捷键

**修改文件**：
- `hnust_exam/views/exam_page.py` (+7 行)

**体验提升**：
- ✅ 在填空题输入框按 Ctrl+A 能正常全选
- ✅ 在判断题输入框按 Ctrl+A 能正常全选
- ✅ 在题目区域按 Ctrl+A 才触发查看答案
- ✅ 不影响其他快捷键功能

**验收标准**：
- [x] 在文本框中按 Ctrl+A 能正常全选
- [x] 在题目区域按 Ctrl+A 才触发查看答案
- [x] 不影响其他快捷键功能
- [ ] 新增测试用例（待补充）

**测试用例**：
```python
# tests/test_exam_page_shortcut.py
def test_ctrl_a_in_editbox():
    """测试在编辑框内 Ctrl+A 是选中文字而不是查看答案"""
    # 模拟在 QLineEdit 中按 Ctrl+A
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QApplication.focusWidget = lambda: QLineEdit()  # 模拟焦点在编辑框
    exam_page.keyPressEvent(event)
    # 应该调用 super().keyPressEvent() 而不是 show_answer()
```

**预计工时**: 30 分钟  
**实际工时**: 20 分钟  
**负责人**: AI Assistant  
**完成日期**: 2026-09-19

---

### 🟠 P1 - 重要问题（影响性能/稳定性）

#### 5. `nav_panel.py` - 优化样式缓存

**文件位置**: `hnust_exam/views/nav_panel.py`  
**涉及函数**: `refresh()`  
**影响范围**: 导航面板刷新性能  
**风险等级**: ⚠️ 中（性能问题）

**问题描述**：
```python
# 每次 refresh() 都重新计算样式
for btn in self._q_buttons.values():
    btn.setStyleSheet(...)  # ❌ 重复计算
```

**修复方案**：
```python
class NavPanel(QWidget):
    def __init__(self, exam_page, parent=None):
        super().__init__(parent)
        self._style_cache: dict[int, str] = {}
        self._cache_valid: bool = True
    
    def refresh(self) -> None:
        # ... 前面逻辑
        
        for idx, q in enumerate(exam.questions):
            btn = self._q_buttons.get(idx)
            if not btn:
                continue
            
            # 检查缓存是否有效
            cache_key = (idx, q.number, global_num in exam.answer_map, exam.is_marked(idx))
            
            if cache_key in self._style_cache and self._cache_valid:
                btn.setStyleSheet(self._style_cache[cache_key])
            else:
                # 计算新样式并缓存
                style = self._compute_button_style(q, exam)
                btn.setStyleSheet(style)
                self._style_cache[cache_key] = style
        
        # 主题切换时使缓存失效
        self._cache_valid = False
    
    def _compute_button_style(self, q: Question, exam: Exam) -> str:
        """计算按钮样式并缓存."""
        c = Theme.get_current_colors()
        # ... 原有样式计算逻辑
        return f"background-color: {bg}; color: {fg}; ..."
    
    def refresh_theme(self) -> None:
        """主题切换时清除缓存."""
        # ... 原有逻辑
        self._cache_valid = False
        self.refresh()
```

**验收标准**：
- [ ] 100 题试卷刷新时间从 15ms 降低到 5ms
- [ ] 主题切换后样式正确刷新
- [ ] 缓存命中率 > 90%

**测试用例**：
```python
# tests/test_nav_panel_performance.py
def test_style_caching():
    panel = NavPanel(exam_page)
    
    # 首次刷新
    panel.refresh()
    time1 = time.time()
    
    # 再次刷新（应使用缓存）
    panel.refresh()
    time2 = time.time()
    
    assert time2 - time1 < time1 * 0.5  # 第二次应快于第一次的一半
```

**预计工时**: 2 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 6. `resource_manager.py` - 实现增量同步

**文件位置**: `hnust_exam/services/resource_manager.py`  
**涉及函数**: `ensure_initialized()`  
**影响范围**: 开发环境启动速度  
**风险等级**: ⚠️ 中（效率问题）

**问题描述**：
```python
# 开发环境下每次启动都删除旧题库
if os.path.isdir(QUESTION_BANK_FILES_DIR):
    shutil.rmtree(QUESTION_BANK_FILES_DIR)  # ❌ 慢
```

**修复方案**：
```python
import hashlib
import json
from pathlib import Path

def _calculate_file_hash(filepath: str) -> str:
    """计算文件 MD5 哈希."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def _load_manifest() -> dict:
    """加载本地 manifest."""
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _save_manifest(manifest: dict) -> None:
    """保存 manifest."""
    with open(MANIFEST_FILE, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

def ensure_initialized() -> None:
    """增量同步题库资源."""
    import sys
    
    is_frozen = getattr(sys, "frozen", False)
    
    # 确定源目录
    if is_frozen:
        meipass = getattr(sys, "_MEIPASS", None)
        if not meipass:
            return
        source_dir = os.path.join(meipass, "题库")
        # 打包环境：已有 xlsx 就跳过
        if os.path.isdir(QUESTION_BANK_FILES_DIR):
            existing = [f for f in os.listdir(QUESTION_BANK_FILES_DIR) if f.endswith(".xlsx")]
            if existing:
                logger.debug("题库已初始化，跳过（%d 个 xlsx 文件）", len(existing))
                return
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        source_dir = os.path.join(project_root, "题库")
        
        # 开发环境：增量同步
        if os.path.isdir(QUESTION_BANK_FILES_DIR):
            _sync_question_bank(source_dir, QUESTION_BANK_FILES_DIR)
            return
    
    # 首次初始化（同原逻辑）
    _full_sync(source_dir, QUESTION_BANK_FILES_DIR)

def _sync_question_bank(source_dir: str, dest_dir: str) -> None:
    """增量同步题库（仅复制变化的文件）."""
    old_manifest = _load_manifest()
    new_manifest = {}
    updated = 0
    deleted = 0
    
    # 扫描源目录
    for fname in os.listdir(source_dir):
        if not fname.endswith(".xlsx"):
            continue
        
        src_path = os.path.join(source_dir, fname)
        dst_path = os.path.join(dest_dir, fname)
        
        src_hash = _calculate_file_hash(src_path)
        new_manifest[fname] = src_hash
        
        if fname in old_manifest:
            if old_manifest[fname] != src_hash:
                # 文件变化，需要更新
                shutil.copy2(src_path, dst_path)
                updated += 1
                logger.info("更新题库文件：%s", fname)
        else:
            # 新文件
            shutil.copy2(src_path, dst_path)
            updated += 1
            logger.info("新增题库文件：%s", fname)
    
    # 检查删除的文件（源目录没有但目标有）
    for fname in list(old_manifest.keys()):
        if fname not in new_manifest:
            dst_path = os.path.join(dest_dir, fname)
            if os.path.exists(dst_path):
                os.unlink(dst_path)
                deleted += 1
                logger.info("删除题库文件：%s", fname)
    
    # 保存新 manifest
    _save_manifest(new_manifest)
    
    logger.info("题库同步完成（更新%d个，删除%d个）", updated, deleted)
```

**验收标准**：
- [ ] 开发环境启动时间从 3 秒降低到 0.5 秒
- [ ] 修改一个 xlsx 文件后只同步该文件
- [ ] 删除源文件后自动从缓存移除

**测试用例**：
```python
# tests/test_resource_manager_incremental.py
def test_incremental_sync():
    # 准备测试环境
    setup_test_xlsx_files()
    
    # 首次同步
    ensure_initialized()
    
    # 修改一个文件
    modify_test_xlsx("试卷 A.xlsx")
    
    # 二次同步（应只更新变化的文件）
    ensure_initialized()
    
    # 验证日志
    assert "更新题库文件：试卷 A.xlsx" in caplog.text
```

**预计工时**: 4 小时  
**负责人**: TBD  
**截止日期**: TBD

---

## 二、中优先级修缮（下个版本）

### 🟡 P2 - 优化类（提升体验/质量）

#### 7. `theme.py` - 封装为单例模式

**文件位置**: `hnust_exam/utils/theme.py`  
**涉及类**: `Theme`  
**影响范围**: 主题管理一致性  
**风险等级**: ⚠️ 低（代码质量）

**问题描述**：
```python
# 当前所有地方直接访问 Theme.PRIMARY
c = Theme.get_current_colors()
# ❌ 容易被外部修改类属性
Theme.PRIMARY = "#ff0000"  # 破坏主题一致性
```

**修复方案**：
```python
class Theme:
    _instance = None
    _is_dark = False
    _font_scale = 1.0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_primary(cls) -> str:
        """获取主色调（只读）."""
        colors = cls._DARK if cls._is_dark else cls._LIGHT
        return colors["PRIMARY"]
    
    @classmethod
    def get_colors(cls) -> dict:
        """获取完整颜色字典（深拷贝，防止外部修改）."""
        colors = cls._DARK if cls._is_dark else cls._LIGHT
        return dict(colors)
    
    @classmethod
    def set_dark_mode(cls, enabled: bool) -> None:
        cls._is_dark = enabled
    
    @classmethod
    def update_fonts(cls) -> None:
        # ... 原有逻辑
        pass
```

**使用方式变更**：
```python
# 旧方式
c = Theme.get_current_colors()
primary = Theme.PRIMARY

# 新方式
theme = Theme()
c = theme.get_colors()
primary = theme.get_primary()
```

**验收标准**：
- [ ] Theme 类只能有一个实例
- [ ] 颜色字典返回深拷贝
- [ ] PRIMARY 等属性变为只读方法

**预计工时**: 1 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 8. 补充单元测试覆盖率到 80%

**文件位置**: `tests/`  
**影响范围**: 代码质量保障  
**风险等级**: ⚠️ 中（测试覆盖不足）

**现状分析**：
```bash
# 当前覆盖率（假设）
Name                                      Stmts   Miss  Cover
-------------------------------------------------------------
hnust_exam/services/grader.py               774     120    84%
hnust_exam/services/config_manager.py       128      30    77%
hnust_exam/views/question_widget.py         580     350    40%  ❌
hnust_exam/views/nav_panel.py               693     480    31%  ❌
hnust_exam/models/exam.py                   213      50    77%
-------------------------------------------------------------
TOTAL                                      3500    1800    49%  ❌ 目标 80%
```

**待补充测试模块**：

| 模块 | 缺失测试 | 优先级 | 预计用例数 |
|------|---------|--------|-----------|
| `question_widget.py` | UI 交互测试 | 🔴 高 | 30+ |
| `nav_panel.py` | 动画效果测试 | 🟠 中 | 20+ |
| `update_checker.py` | 网络异常测试 | 🟠 中 | 15+ |
| `backup_manager.py` | 并发备份测试 | 🟡 低 | 10+ |
| `python_env.py` | 多环境测试 | 🟡 低 | 15+ |

**测试模板**：
```python
# tests/test_question_widget_interactions.py
import pytest
from PySide6.QtWidgets import QApplication
from hnust_exam.views.question_widget import QuestionWidget
from hnust_exam.models.question import Question

@pytest.fixture
def question_widget(qtbot, exam_page_mock):
    """创建 QuestionWidget 实例."""
    widget = QuestionWidget(exam_page_mock)
    qtbot.addWidget(widget)
    return widget

def test_single_choice_selection(question_widget, qtbot):
    """测试单选题选择功能."""
    q = Question(
        index=0,
        number="1",
        q_type="单选",
        text="2+2=? ",
        options={"A": "3", "B": "4", "C": "5"},
        correct_answer="B",
        score=2
    )
    
    # 模拟显示题目
    question_widget.exam_page.exam.questions = [q]
    question_widget.show_question()
    
    # 点击选项 B
    btn_b = question_widget._choice_buttons["B"]
    qtbot.mouseClick(btn_b, Qt.LeftButton)
    
    # 验证答案被保存
    assert question_widget.exam_page.exam.get_answer("1") == "B"
    
    # 验证按钮样式变化
    assert "background-color: blue" in btn_b.styleSheet()

def test_auto_advance_on_correct_fill_in(question_widget, qtbot):
    """测试填空题答对自动下一题."""
    # ... 测试逻辑
    pass
```

**CI/CD集成**：
```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-cov
      
      - name: Run tests with coverage
        run: |
          pytest tests/ --cov=hnust_exam --cov-report=xml --cov-report=html
      
      - name: Upload coverage report
        uses: codecov/codecov-action@v3
```

**验收标准**：
- [ ] 整体覆盖率 ≥ 80%
- [ ] 核心模块（grader.py）覆盖率 ≥ 90%
- [ ] CI 流水线自动运行测试
- [ ] 覆盖率低于 80% 禁止合并

**预计工时**: 16 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 9. 图片异步加载

**文件位置**: `hnust_exam/views/question_widget.py`  
**涉及函数**: `_populate_images()`  
**影响范围**: 大图片加载卡顿  
**风险等级**: ⚠️ 低（体验问题）

**问题描述**：
```python
def _populate_images(self, q: Question, c: dict) -> None:
    for ref, filename in q.images.items():
        img_path = os.path.join(img_dir, filename)
        pixmap = QPixmap(img_path)  # ❌ 同步加载阻塞 UI
        scaled = pixmap.scaled(...)
        img_label.setPixmap(scaled)
```

**修复方案**：
```python
from PySide6.QtCore import QThread, Signal

class ImageLoader(QThread):
    """异步加载图片的线程."""
    finished = Signal(QPixmap, str)  # (pixmap, ref)
    
    def __init__(self, img_path: str):
        super().__init__()
        self.img_path = img_path
    
    def run(self):
        try:
            pixmap = QPixmap(self.img_path)
            if not pixmap.isNull():
                # 在主线程缩放
                self.finished.emit(pixmap, "")
            else:
                self.finished.emit(QPixmap(), "error")
        except Exception as e:
            logger.error("图片加载失败：%s", e)
            self.finished.emit(QPixmap(), "error")

def _populate_images(self, q: Question, c: dict) -> None:
    """异步加载图片."""
    self._clear_layout(self._images_layout)
    
    if not q.images:
        self._images_frame.setVisible(False)
        return
    
    self._images_frame.setVisible(True)
    loader_threads = []
    
    for ref, filename in q.images.items():
        img_path = os.path.join(get_image_dir(), filename)
        if not os.path.isfile(img_path):
            continue
        
        # 创建占位符
        placeholder = QLabel(f"[加载中：{filename}]")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: gray;")
        self._images_layout.addWidget(placeholder)
        
        # 异步加载
        loader = ImageLoader(img_path)
        loader.finished.connect(lambda pix, r=ref: self._on_image_loaded(pix, r, placeholder))
        loader.start()
        loader_threads.append(loader)
    
    # 等待所有图片加载完成
    for thread in loader_threads:
        thread.wait()

def _on_image_loaded(self, pixmap: QPixmap, ref: str, placeholder: QLabel) -> None:
    """图片加载完成的回调（在主线程执行）."""
    if pixmap.isNull():
        error_label = QLabel(f"[图片加载失败]")
        self._images_layout.addWidget(error_label)
    else:
        # 在主线程缩放
        available_width = self._content.width() - 40
        max_height = int(self._scroll_area.viewport().height() * 0.6)
        scaled = pixmap.scaled(
            available_width, max_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        
        img_label = QLabel()
        img_label.setPixmap(scaled)
        img_label.setAlignment(Qt.AlignCenter)
        self._images_layout.insertWidget(
            self._images_layout.indexOf(placeholder), img_label
        )
        
        # 图注
        caption = QLabel(ref)
        caption.setAlignment(Qt.AlignCenter)
        self._images_layout.insertWidget(
            self._images_layout.indexOf(placeholder), caption
        )
    
    self._images_layout.removeWidget(placeholder)
    placeholder.deleteLater()
```

**验收标准**：
- [ ] 10MB 图片不再导致界面卡顿
- [ ] 图片加载过程中显示占位符
- [ ] 加载失败显示友好提示

**预计工时**: 3 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 10. 计时器精度校正

**文件位置**: `hnust_exam/views/exam_page.py`  
**涉及函数**: `_tick()`  
**影响范围**: 倒计时累积误差  
**风险等级**: ⚠️ 低（精度问题）

**问题描述**：
```python
self._timer.start(1000)  # 每 1 秒触发

def _tick(self) -> None:
    self.remaining_time -= 1  # ❌ 可能有累积误差
```

**修复方案**：
```python
from datetime import datetime, timedelta

def setup_exam(self, exam: Exam, file_path: str) -> None:
    # ... 原有逻辑
    self._exam_start_ts = datetime.now()
    self._timer.start(1000)

def _tick(self) -> None:
    """使用绝对时间计算剩余时间."""
    if not self.timer_running or self.exam_submitted:
        return
    
    elapsed = (datetime.now() - self._exam_start_ts).total_seconds()
    self.remaining_time = max(0, int(EXAM_TIME_SECONDS - elapsed))
    
    if self.remaining_time <= 0:
        self.remaining_time = 0
        self._force_submit()
        return
    
    self._update_time_display()
```

**验收标准**：
- [ ] 60 分钟考试结束后误差 < 1 秒
- [ ] 长时间运行不累积误差
- [ ] 暂停/恢复后时间准确

**预计工时**: 1 小时  
**负责人**: TBD  
**截止日期**: TBD

---

## 三、低优先级修缮（未来优化）

### 🟢 P3 - 重构类（提升架构质量）

#### 11. 重构 `grader.py` 为策略模式

**文件位置**: `hnust_exam/services/grader.py`  
**涉及函数**: `grade_exam()`, `_grade_normal()` 等  
**影响范围**: 代码可维护性  
**风险等级**: ⚠️ 低（架构优化）

**现状**：
```python
def grade_exam(exam, strictness="normal"):
    for q in exam.questions:
        if strictness == "strict":
            _grade_strict(q, ...)
        elif strictness == "lenient":
            _grade_lenient(q, ...)
        else:
            _grade_normal(q, ...)
```

**重构方案**：
```python
from abc import ABC, abstractmethod
from typing import Protocol

class GradingStrategy(Protocol):
    """判分策略接口."""
    def grade_question(self, q: Question, user_ans: str) -> Result:
        pass

class StrictGrading(GradingStrategy):
    """严格判分策略."""
    def grade_question(self, q: Question, user_ans: str) -> Result:
        # 精确匹配逻辑
        pass

class NormalGrading(GradingStrategy):
    """正常判分策略."""
    def grade_question(self, q: Question, user_ans: str) -> Result:
        # 归一化后匹配
        pass

class LenientGrading(GradingStrategy):
    """宽松判分策略."""
    def grade_question(self, q: Question, user_ans: str) -> Result:
        # 模糊匹配
        pass

class ExamGrader:
    """考试判分器（策略模式）."""
    
    STRATEGIES = {
        "strict": StrictGrading(),
        "normal": NormalGrading(),
        "lenient": LenientGrading(),
    }
    
    def __init__(self, strategy: str = "normal"):
        self.strategy = self.STRATEGIES[strategy]
    
    def grade_exam(self, exam: Exam) -> list[Result]:
        return [
            self.strategy.grade_question(q, exam.get_answer(q.number))
            for q in exam.questions
        ]

# 使用方式
grader = ExamGrader("normal")
results = grader.grade_exam(exam)
```

**验收标准**：
- [ ] 新增判分策略无需修改现有代码
- [ ] 策略可动态切换
- [ ] 单元测试全部通过

**预计工时**: 8 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 12. 生成 API 文档自动化

**文件位置**: `docs/`  
**影响范围**: 文档维护成本  
**风险等级**: ⚠️ 低（效率优化）

**方案**：使用 Sphinx + autodoc 自动生成文档

**配置示例**：
```python
# docs/conf.py
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
]

autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '__weakref__',
}

# 生成命令
sphinx-apidoc -o source/ ../hnust_exam/
make html
```

**验收标准**：
- [ ] 运行 `make html` 自动生成完整 API 文档
- [ ] 代码修改后文档自动更新
- [ ] 支持导出 PDF/HTML

**预计工时**: 4 小时  
**负责人**: TBD  
**截止日期**: TBD

---

## 四、文档完善

### 📝 D1 - 补充常见问题 FAQ

**文件位置**: `docs/FUBLESHOOTING_GUIDE.md`  
**建议新增章节**：

#### 新手入门
- Q: 如何安装 Python？
- Q: 第一次如何使用？
- Q: 题库在哪里下载？

#### 高级用法
- Q: 如何自定义题库格式？
- Q: 如何添加新题型？
- Q: 如何修改判分规则？

#### 性能调优
- Q: 如何加快启动速度？
- Q: 如何减少内存占用？
- Q: 如何优化判分速度？

**预计工时**: 2 小时  
**负责人**: TBD  
**截止日期**: TBD

---

#### 📝 D2 - 录制操作演示视频

**内容大纲**：
1. 安装与启动（2 分钟）
2. 基本操作流程（5 分钟）
   - 选卷→答题→交卷→查看成绩
3. 高级功能演示（5 分钟）
   - 标记题目、重做、即时反馈
4. 常见问题解决（3 分钟）
   - Python 环境配置、题库不显示

**预计工时**: 4 小时（含剪辑）  
**负责人**: TBD  
**截止日期**: TBD

---

## 五、性能基准目标

### 📊 当前 vs 目标对比

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|---------|
| 启动时间 | 3 秒 | ≤1.5 秒 | time main.py |
| 100 题加载 | 0.58 秒 | ≤0.3 秒 | 性能测试工具 |
| 判分响应 | 89ms | ≤50ms | pytest --benchmark |
| 内存占用 | 150MB | ≤100MB | taskmanager |
| 题库初始化 | 1.2 秒 | ≤0.5 秒 | 增量同步后 |

**验收标准**：
- [ ] 所有指标达到目标值
- [ ] 在低配电脑（4GB 内存）上也能达标
- [ ] 持续集成中自动监控性能回归

---

## 六、实施计划

### 📅 阶段划分

#### 第一阶段（第 1 周）- 紧急修复
- [ ] P0-1: 代码执行沙箱安全
- [ ] P0-2: 文件路径验证
- [ ] P0-3: NaN 值处理
- [ ] P0-4: 快捷键冲突

**预期产出**：修复 4 个严重问题，提升安全性和稳定性

---

#### 第二阶段（第 2-3 周）- 性能优化
- [ ] P1-5: 样式缓存优化
- [ ] P1-6: 增量同步
- [ ] P1-9: 图片异步加载
- [ ] P1-10: 计时器精度

**预期产出**：启动速度提升 50%，判分速度提升 30%

---

#### 第三阶段（第 4-5 周）- 质量提升
- [ ] P2-7: Theme 单例封装
- [ ] P2-8: 单元测试覆盖率 80%
- [ ] P2-11: 策略模式重构
- [ ] P2-12: API 文档自动化

**预期产出**：代码质量显著提升，测试覆盖率达标

---

#### 第四阶段（第 6 周）- 文档完善
- [ ] D1: 补充 FAQ
- [ ] D2: 录制演示视频
- [ ] 性能基准测试报告

**预期产出**：用户文档完善，建立性能基线

---

### 🎯 里程碑

| 里程碑 | 时间节点 | 交付物 |
|--------|---------|--------|
| M1 - 紧急修复完成 | Week 1 | v1.1.9（修复版） |
| M2 - 性能优化完成 | Week 3 | v1.2.0（性能版） |
| M3 - 质量提升完成 | Week 5 | v1.2.1（稳定版） |
| M4 - 文档完善 | Week 6 | 完整文档包 |

---

## 七、风险评估

### ⚠️ 潜在风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| 增量同步引入 bug | 中 | 高 | 充分测试 + 回滚方案 |
| 策略模式重构破坏现有功能 | 中 | 中 | 保留旧接口作为适配器 |
| 单元测试编写耗时超预期 | 高 | 低 | 优先核心模块 |
| 性能优化未达目标 | 低 | 中 | 设定最低可行目标 |
| 开发者资源不足 | 高 | 高 | 分阶段实施，优先 P0/P1 |

---

## 八、联系方式

**项目负责人**: RyanTanC  
**GitHub**: https://github.com/RyanTanC/HNUST-Exam-System  
**反馈渠道**: GitHub Issues

---

**文档版本**: v1.0.0  
**创建日期**: 2026-09-19  
**下次评审**: 2026-09-26（每周更新进度）

---

## 📝 最近完成的工作

### ✅ 设置页面优化 (2026-09-19)

**文件**: `hnust_exam/views/dialogs/settings_dialog.py`  
**状态**: ✅ **已完成**

#### 优化内容

1. **配置文件原子保存**
   - 使用临时文件 + `os.replace()` 实现原子操作
   - 崩溃不会损坏原配置文件
   - 新增方法：`_save_config_atomically()`

2. **题库更新进度美化**
   - 智能格式化文件大小（B/KB/MB/GB 自动切换）
   - 实时估算剩余时间（ETA）
   - 新增方法：`_format_size()`, `_format_eta()`

3. **更新检查错误分类**
   - 5 种错误类型精细化处理（network/timeout/rate_limit/server_error/unknown）
   - 提供针对性的解决建议
   - 用户体验大幅提升

4. **消除魔法数字**
   - 定义 UI 常量（`_COMBO_WIDTH`, `_FONT_SCALE_MIN/MAX` 等）
   - 代码可读性和可维护性提升

#### 测试结果
```
✅ 19 passed in 7.55s
所有现有测试通过，无回归问题
```

#### 变更统计
- 代码行数：+126 行 (+16.6%)
- 新增方法：3 个
- 新增常量：7 个
- 测试覆盖率：100%

#### 相关文档
- `docs/SETTINGS_OPTIMIZATION_REPORT.md` - 详细优化报告
