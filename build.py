# 打包脚本 - 解决中文文件名问题

import subprocess
import sys

def main():
    """使用 PyInstaller 打包 HNUST 仿真平台."""
    
    # 检查 Python 环境
    print(f"Python 版本：{sys.version}")
    
    # 构建打包命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--icon", "icon.ico",
        "--name", "HNUST 仿真平台",
        "--add-data", "题库;题库",
        "--add-data", "icon.ico;.",
        "--add-data", "hnust_exam/resources;hnust_exam/resources",
        "--hidden-import", "PySide6.QtCore",
        "--hidden-import", "PySide6.QtGui",
        "--hidden-import", "PySide6.QtWidgets",
        "--hidden-import", "PySide6.QtSvg",
        "--hidden-import", "PySide6.QtSvgWidgets",
        "--hidden-import", "openpyxl",
        "--collect-data", "certifi",
        "--runtime-tmpdir", "%TEMP%\\HNUST_simulation_temp",
        "main.py",
        "--clean"
    ]
    
    print("开始打包...")
    print(f"命令：{' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n✅ 打包完成！")
        print("产物位置：dist/HNUST 仿真平台.exe")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 打包失败：{e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n❌ 找不到 PyInstaller: {e}")
        print("请先安装：pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    main()
