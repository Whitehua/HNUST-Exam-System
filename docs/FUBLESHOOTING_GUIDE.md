# HNUST 仿真平台 - 故障排查手册

## 目录

- [常见问题速查](#常见问题速查)
- [题库相关](#题库相关)
- [Python 环境相关](#python 环境相关)
- [C 语言环境相关](#c 语言环境相关)
- [更新相关](#更新相关)
- [性能问题](#性能问题)
- [崩溃与异常](#崩溃与异常)
- [日志分析](#日志分析)
- [手动修复指南](#手动修复指南)

---

## 常见问题速查

### 🔴 紧急问题（无法启动）

| 症状 | 快速解决方案 |
|------|-------------|
| 双击 exe 无反应 | 检查任务管理器是否有残留进程 |
| 启动后立即闪退 | 查看 `~/Documents/HNUST_Exam_Logs/exam_crash_*.log` |
| 黑屏/白屏 | 按 `F11` 切换全屏，或重启应用 |
| 所有功能不可用 | 删除 `~/.hnust_exam/config.json` 重置设置 |

---

### 🟡 功能问题（能运行但有问题）

| 症状 | 快速解决方案 |
|------|-------------|
| 题库不显示 | 检查 `~/.hnust_exam/question_bank/files/` 是否有 xlsx 文件 |
| Python 题打不开 | 设置→手动指定 Python 路径 |
| 判分不准确 | 设置→调整判分严格度 |
| 更新失败 | 手动下载最新版覆盖安装 |

---

## 题库相关

### 问题 1：题库不显示 / 选卷页为空

#### 现象
- 进入选卷页后列表为空
- 提示"找不到试卷文件"

#### 原因分析
1. 题库未初始化（首次启动）
2. 题库目录被误删
3. 权限不足无法读取
4. 打包时未包含题库资源

#### 排查步骤

**Step 1：检查题库缓存目录**
```bash
# Windows
dir %USERPROFILE%\.hnust_exam\question_bank\files

# 如果目录不存在或为空 → Step 2
# 如果有 xlsx 文件 → Step 3
```

**Step 2：手动初始化题库**
```bash
# 方法 A：重新运行程序（会自动初始化）
HNUST 仿真平台.exe

# 方法 B：从项目源码同步（开发环境）
python -c "from hnust_exam.services.resource_manager import ensure_initialized; ensure_initialized()"
```

**Step 3：验证文件完整性**
```bash
# 应该有至少 20+ 个 xlsx 文件
dir %USERPROFILE%\.hnust_exam\question_bank\files\*.xlsx

# 如果数量为 0 → 题库损坏，重新初始化
# 如果数量正常 → 检查文件扩展名是否为.xlsx
```

**Step 4：检查文件权限**
```bash
# 右键目录→属性→安全
# 确保当前用户有"读取"权限
```

#### 解决方案

**方案 A：自动恢复（推荐）**
1. 关闭程序
2. 删除整个 `~/.hnust_exam` 目录
3. 重新启动程序（会自动重新初始化）

**方案 B：手动复制题库**
```bash
# 从项目根目录复制到 AppData
xcopy "题库\*.xlsx" "%USERPROFILE%\.hnust_exam\question_bank\files\" /Y
xcopy "题库\试题图片\" "%USERPROFILE%\.hnust_exam\question_bank\files\试题图片\" /E /Y
xcopy "题库\试题文件夹\" "%USERPROFILE%\.hnust_exe\question_bank\files\试题文件夹\" /E /Y
```

**方案 C：重新打包（开发者）**
```bash
# 检查.spec 文件的 datas 参数
--add-data "题库;题库"

# 重新打包
pyinstaller HNUST 仿真平台.spec
```

---

### 问题 2：题库更新失败

#### 现象
- 提示"更新失败"
- 版本号不变化
- 下载进度条卡住

#### 原因分析
1. 网络连接超时
2. GitHub/Gitee API 限流
3. 磁盘空间不足
4. 文件被占用

#### 排查步骤

**Step 1：检查网络连通性**
```bash
# 测试 GitHub 访问
ping github.com

# 测试 Gitee 访问
ping gitee.com

# 如果 ping 不通 → 检查防火墙/代理
```

**Step 2：检查磁盘空间**
```bash
# 确保 C 盘至少有 500MB 可用空间
df -h ~  # Linux/Mac
# 或 打开此电脑→查看 C 盘属性
```

**Step 3：查看更新日志**
```bash
type %USERPROFILE%\.hnust_exam\logs\update.log
```

**关键字段检查**：
- `"error": "Timeout"` → 网络问题
- `"error": "Permission denied"` → 权限问题
- `"error": "No space left on device"` → 磁盘满
- `"success": true` → 更新成功

#### 解决方案

**方案 A：手动更新（推荐）**
1. 访问 https://github.com/RyanTanC/HNUST-Exam-System/releases
2. 下载最新 `HNUST 仿真平台.exe`
3. 备份当前配置（`~/.hnust_exam/config.json`）
4. 覆盖安装新 exe
5. 还原配置文件

**方案 B：强制刷新题库**
```bash
# 删除旧题库（会触发重新下载）
rmdir /s %USERPROFILE%\.hnust_exam\question_bank

# 重启程序（自动从 Release 下载最新题库）
HNUST 仿真平台.exe
```

**方案 C：离线更新（无网络环境）**
1. 在有网电脑上下载题库包
```bash
# 从 Release 下载
question_bank.zip
```
2. 解压到 U 盘
3. 复制到目标电脑
```bash
xcopy U:\question_bank\* %USERPROFILE%\.hnust_exam\question_bank\ /E /Y
```

---

### 问题 3：图片无法显示

#### 现象
- 题目中图片显示为"[未找到图片：xxx]"
- 图片区域空白

#### 排查步骤

**Step 1：检查图片目录**
```bash
dir %USERPROFILE%\.hnust_exam\question_bank\files\试题图片
```

**Step 2：验证文件名匹配**
```bash
# Excel 中的图片列格式：图片 1=file1.gif;图片 2=file2.jpg
# 实际文件名必须完全一致（包括大小写和扩展名）
```

**Step 3：检查图片格式**
```bash
# 支持的格式：.jpg, .jpeg, .png, .gif, .bmp
# 不支持：.webp, .svg, .tiff（需转换）
```

#### 解决方案

**方案 A：重新复制图片**
```bash
# 从项目题库目录复制
xcopy "题库\试题图片\*" "%USERPROFILE%\.hnust_exam\question_bank\files\试题图片\" /Y
```

**方案 B：修复 Excel 图片列**
1. 打开对应 Excel 文件
2. 检查"图片"列格式是否正确
3. 确保文件名与实际文件一致
4. 保存并重新加载

---

## Python 环境相关

### 问题 1：Python 找不到 / IDLE 打不开

#### 现象
- 点击"答题"按钮无反应
- 提示"未检测到 Python 环境"
- 程序题无法打开

#### 原因分析
1. 未安装 Python
2. Python 不在 PATH 中
3. IDLE 模块缺失
4. 多版本冲突

#### 排查步骤

**Step 1：检查 Python 是否安装**
```bash
# 命令行测试
python --version
py --version

# 如果提示"不是内部或外部命令" → 未安装或不在 PATH
```

**Step 2：检查 IDLE 是否可用**
```bash
# 测试 IDLE 模块
python -m idlelib

# 如果报错"ModuleNotFoundError: No module named 'idlelib'" 
# → Python 安装不完整（选择时未勾选 IDLE）
```

**Step 3：查找所有 Python 安装**
```bash
# 搜索注册表
reg query "HKLM\SOFTWARE\Python\PythonCore"

# 搜索常见路径
dir "C:\Program Files\Python*"
dir "C:\Users\*\AppData\Local\Programs\Python\"
```

#### 解决方案

**方案 A：手动指定 Python 路径（推荐）**
1. 打开程序→设置→Python 环境
2. 点击"浏览"
3. 选择 Python 可执行文件（如 `C:\Python311\python.exe`）
4. 点击"完成"

**常用路径参考**：
```
C:\Python311\python.exe
C:\Program Files\Python311\python.exe
C:\Users\用户名\AppData\Local\Programs\Python\Python311\python.exe
C:\Users\用户名\AppData\Local\Microsoft\WindowsApps\python.exe  # Microsoft Store 版
```

**方案 B：重新安装 Python**
1. 访问 https://www.python.org/downloads/
2. 下载最新版 Python 3.11+
3. **关键**：安装时勾选 "Add Python to PATH"
4. 勾选 "Install idle" 和 "Install pip"
5. 重启程序

**方案 C：使用 py  launcher**
```bash
# Windows 自带 py  launcher（Win10 1803+）
py -3 --version

# 如果可用，程序会自动识别
```

---

### 问题 2：程序题判分不准确

#### 现象
- 答案正确但判错
- 空格差异导致错误
- 注释影响判分

#### 原因分析
1. 判分严格度过高
2. 代码格式差异
3. 注释未剥离

#### 解决方案

**方案 A：调整判分严格度**
1. 打开设置
2. 找到"判分严格度"
3. 选择：
   - `normal`（默认）：归一化 + 精确匹配
   - `lenient`：允许 85% 相似度
   - `strict`：严格精确匹配

**方案 B：标准化代码格式**
```python
# 避免以下写法（容易判错）
def foo( x ) :      # ❌ 多余空格
    return x + 1     # ❌ 缩进不一致

# 推荐写法
def foo(x):          # ✅ 紧凑格式
    return x + 1     # ✅ 统一缩进（4 空格）
```

**方案 C：移除无关注释**
```python
# 参考答案
def fib(n):
    if n <= 1:
        return n
    return fib(n-1) + fib(n-2)

# 你的答案（带注释）
def fib(n):
    # 基本情况
    if n <= 1:
        return n
    # 递归情况
    return fib(n-1) + fib(n-2)

# 系统会自动剥离注释，所以可以保留
```

---

## C 语言环境相关

### 问题 1：.c 文件无法打开

#### 现象
- 点击"答题"按钮提示"未找到合适的 C 语言编辑器"
- VC++ 2010 Express 找不到
- VS Code 打不开

#### 排查步骤

**Step 1：检查已安装编辑器**
```bash
# VC++ 2010 Express
dir "C:\Program Files (x86)\Microsoft Visual Studio 10.0\Common7\IDE\VCExpress.exe"

# VS Code
dir "C:\Users\*\AppData\Local\Programs\Microsoft VS Code\Code.exe"
```

**Step 2：检查 PATH 环境变量**
```bash
# 是否包含 code.cmd 或 vcexpress.exe
echo %PATH%
```

#### 解决方案

**方案 A：安装 VS Code（推荐）**
1. 访问 https://code.visualstudio.com/
2. 下载安装
3. 安装时勾选 "Add to PATH"
4. 重启程序

**方案 B：安装 VC++ 2010 Express**
1. 下载 VC++ 2010 Express（ISO 镜像）
2. 挂载并安装
3. 重启程序

**方案 C：使用系统默认编辑器**
```bash
# 将.c 文件关联到记事本/其他编辑器
# 右键.c 文件→打开方式→选择程序
```

---

### 问题 2：C 程序编译失败

#### 现象
- 提示"gcc 不是内部或外部命令"
- 编译错误
- 链接错误

#### 解决方案

**方案 A：安装 MinGW-w64**
1. 访问 https://winlibs.com/
2. 下载 UCRT 版本（推荐）
3. 解压到 `C:\mingw64`
4. 添加环境变量：
   ```
   PATH 追加：C:\mingw64\bin
   ```
5. 验证安装：
   ```bash
   gcc --version
   ```

**方案 B：使用在线编译器**
- 临时替代方案：在本地 IDE 编写，复制答案到系统

---

## 更新相关

### 问题 1：自动更新失败

#### 现象
- 弹窗提示"更新失败"
- 下载进度条卡住
- 替换后无法启动

#### 排查步骤

**Step 1：检查日志**
```bash
type %USERPROFILE%\.hnust_exam\logs\update.log
```

**Step 2：检查文件权限**
```bash
# 右键 exe→属性→安全
# 确保当前用户有"修改"权限
```

**Step 3：检查杀毒软件**
```
某些杀毒软件会拦截 exe 替换操作
暂时禁用后重试
```

#### 解决方案

**方案 A：手动更新（最可靠）**
1. 访问 Release 页面
2. 下载最新 exe
3. 停止当前运行进程（任务管理器）
4. 覆盖安装
5. 重启

**方案 B：清理残留文件**
```bash
# 删除旧的备份文件
del "%TEMP%\*.old.bak"

# 删除 staging 目录
rmdir /s "%TEMP%\HNUST_update_staging"
```

---

### 问题 2：版本回退

#### 场景
- 新版本有 bug，想退回旧版本
- 题库更新后出现兼容性问题

#### 解决方案

**方案 A：保留旧版安装包**
```bash
# 更新前先备份当前 exe
copy HNUST 仿真平台.exe backup\HNUST_v1.1.8.exe
```

**方案 B：从 GitHub Releases 下载历史版本**
1. 访问 https://github.com/RyanTanC/HNUST-Exam-System/releases
2. 找到想要的版本 tag
3. 下载对应的 exe
4. 覆盖安装

**方案 C：跳过新版本更新**
```
设置→更新检查→跳过此版本
下次启动不会再次提示
```

---

## 性能问题

### 问题 1：启动慢 / 加载慢

#### 现象
- 启动超过 5 秒
- 切换试卷卡顿
- 导航面板响应慢

#### 排查步骤

**Step 1：检查题库规模**
```bash
# 统计 xlsx 文件数量
dir %USERPROFILE%\.hnust_exam\question_bank\files\*.xlsx /b | find /c ""

# 如果超过 200 个 → 考虑分批使用
```

**Step 2：检查硬件性能**
```
硬盘类型：SSD vs HDD（HDD 会明显慢）
内存大小：建议 8GB+
CPU：双核以上
```

#### 优化方案

**方案 A：减少题库数量**
```bash
# 只保留常用的试卷
# 不常用的移到其他文件夹
move %USERPROFILE%\.hnust_exam\question_bank\files\不用的.xlsx D:\backup\
```

**方案 B：清理缓存**
```bash
# 删除旧的日志文件
del %USERPROFILE%\.hnust_exam\logs\*.log

# 清空临时文件
del %TEMP%\HNUST_*
```

**方案 C：禁用遥测**
```
设置→高级→关闭匿名使用统计
（减少网络请求）
```

---

### 问题 2：判分响应慢

#### 现象
- 交卷后等待超过 2 秒
- 大量程序题时卡死

#### 优化方案

**方案 A：减少程序题数量**
- 纯理论试卷判分更快

**方案 B：降低判分严格度**
- `strict` 模式需要更多校验

**方案 C：分批判分**
```python
# 开发者选项：启用并行判分
# 需要修改 grader.py 实现
```

---

## 崩溃与异常

### 问题 1：程序闪退

#### 现象
- 启动时立即退出
- 使用过程中突然关闭
- 无错误提示

#### 排查步骤

**Step 1：查看崩溃日志**
```bash
# 位置：~/Documents/HNUST_Exam_Logs/exam_crash_*.log
type ~/Documents/HNUST_Exam_Logs/exam_crash_20260919_123456.log
```

**Step 2：分析错误类型**
```
KeyError: 'xxx'              → Excel 缺少列
FileNotFoundError            → 资源文件丢失
UnicodeDecodeError           → 编码问题
MemoryError                  → 内存不足
```

**Step 3：检查系统兼容性**
```
Windows 版本：Win10 1803+
.NET Framework：4.8+
Visual C++ Redistributable：2015-2022
```

#### 解决方案

**方案 A：重置配置**
```bash
# 重命名配置目录（相当于重置）
rename %USERPROFILE%\.hnust_exam %USERPROFILE%\.hnust_exam.backup

# 重启程序（自动生成新配置）
```

**方案 B：兼容模式运行**
```
右键 exe→属性→兼容性
✓ 以兼容模式运行这个程序（Windows 8）
✓ 以管理员身份运行
```

**方案 C：重新安装**
```bash
# 彻底卸载
rmdir /s %USERPROFILE%\.hnust_exam

# 重新下载最新版 exe
```

---

### 问题 2：数据损坏

#### 现象
- 答题进度丢失
- 配置异常
- 题库 manifest 错误

#### 解决方案

**方案 A：从备份恢复**
```bash
# 检查是否有备份
dir %USERPROFILE%\.hnust_exam\*.backup

# 恢复
copy %USERPROFILE%\.hnust_exam\config.json.backup %USERPROFILE%\.hnust_exam\config.json
```

**方案 B：手动修复 JSON**
```bash
# 使用在线 JSON 校验工具
https://jsonlint.com/

# 修复语法错误后保存
```

**方案 C：重建题库**
```bash
# 删除损坏的 manifest
del %USERPROFILE%\.hnust_exam\question_bank\manifest.json

# 重启程序（自动重新生成）
```

---

## 日志分析

### 日志文件位置

| 日志类型 | 路径 | 说明 |
|---------|------|------|
| 应用日志 | `%USERPROFILE%\.hnust_exam\logs\update.log` | 日常运行日志 |
| 崩溃日志 | `~/Documents/HNUST_Exam_Logs/exam_crash_*.log` | 异常堆栈 |
| 更新日志 | `%USERPROFILE%\.hnust_exam\logs\update.log` | 更新过程记录 |
| 遥测队列 | `%USERPROFILE%\.hnust_exam\telemetry_queue.json` | 待发送统计数据 |

---

### 日志级别说明

| 级别 | 标识 | 含义 |
|------|------|------|
| INFO | `[INFO]` | 一般信息（启动、配置加载等） |
| WARNING | `[WARNING]` | 警告（非致命问题） |
| ERROR | `[ERROR]` | 错误（功能失效） |
| CRITICAL | `[CRITICAL]` | 严重错误（崩溃前） |

---

### 常见日志条目

**正常启动**：
```
2026-09-19 12:34:56 [INFO] hnust_exam: 应用启动，版本：v1.1.8
2026-09-19 12:34:56 [INFO] hnust_exam: 题库已初始化，跳过（128 个 xlsx 文件）
2026-09-19 12:34:57 [INFO] hnust_exam: 更新检查完成：已是最新版本
```

**更新成功**：
```
2026-09-19 12:34:56 [INFO] updater: 检测到新版本：v1.1.9
2026-09-19 12:35:02 [INFO] updater: 下载完成，大小校验通过
2026-09-19 12:35:05 [INFO] updater: 替换成功，正在重启...
```

**错误示例**：
```
2026-09-19 12:34:56 [ERROR] resource_manager: 题库初始化失败：PermissionError
2026-09-19 12:34:57 [WARNING] python_env: 未找到 Python 环境，部分功能受限
```

---

## 手动修复指南

### 终极修复方案（重置一切）

#### 步骤 1：完全卸载
```bash
# 删除应用数据
rmdir /s /q %USERPROFILE%\.hnust_exam

# 删除文档日志
rmdir /s /q "%USERPROFILE%\Documents\HNUST_Exam_Logs"

# 删除桌面快捷方式
del "%USERPROFILE%\Desktop\HNUST 仿真平台.lnk"
```

#### 步骤 2：清理注册表（可选）
```bash
# 打开 regedit
# 删除以下键值（如果存在）
HKEY_CURRENT_USER\Software\RyanTanC\HNUST 仿真平台
HKEY_LOCAL_MACHINE\SOFTWARE\RyanTanC\HNUST 仿真平台
```

#### 步骤 3：重新安装
```bash
# 下载最新版 exe
# 双击运行
# 首次启动会自动初始化题库
```

#### 步骤 4：验证修复
```
✓ 启动时间 < 3 秒
✓ 题库显示正常
✓ 能够答题
✓ 判分正常
✓ 成绩页显示
```

---

### 开发者调试模式

#### 启用详细日志
```bash
# 命令行启动
set QT_LOGGING_RULES="*.debug=true"
python main.py
```

#### 单步调试
```bash
# PyCharm 配置
Run → Edit Configurations → Script path: main.py
Working directory: %PROJECT_DIR%
```

#### 模拟崩溃
```python
# 在 app.py 中添加
if os.environ.get("DEBUG_CRASH"):
    raise Exception("模拟崩溃测试")
```

---

## 联系支持

### 反馈渠道

1. **GitHub Issues**
   - https://github.com/RyanTanC/HNUST-Exam-System/issues
   - 提交问题前请搜索是否已有类似 issue

2. **频道私信**
   - QQ 群：XXXXXXX（请填写实际群号）
   - 提供以下信息：
     - 操作系统版本
     - 软件版本号
     - 问题描述
     - 相关日志片段

### 问题模板

```markdown
## 问题描述
[清晰描述问题现象]

## 复现步骤
1. ...
2. ...
3. ...

## 预期行为
[应该发生什么]

## 实际行为
[实际发生了什么]

## 环境信息
- 操作系统：Windows 11 22H2
- 软件版本：v1.1.8
- Python 版本：3.11.4

## 日志摘要
[粘贴关键错误日志]
```

---

**文档版本**: v1.1.8  
**最后更新**: 2026-09-19  
**维护者**: RyanTanC
