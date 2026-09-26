"""渲染质量配置工具.

提供全局渲染质量的设置和应用功能，包括：
- 抗锯齿
- 文本平滑
- 图片缩放
- 高 DPI 支持
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def apply_render_quality(app: QApplication) -> None:
    """应用全局渲染质量配置.
    
    此函数应在 QApplication 创建后立即调用。
    
    Args:
        app: QApplication 实例
    """
    # 1. 启用高 DPI 自动缩放（必须在创建 QApplication 前或后尽快设置）
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # 2. 启用高级合成效果 - 通过 QSurfaceFormat
    try:
        from PySide6.QtGui import QSurfaceFormat
        
        fmt = QSurfaceFormat()
        fmt.setSampleBuffers(True)  # 启用多重采样缓冲
        fmt.setSamples(4)            # 4x 多重采样
        QSurfaceFormat.setDefaultFormat(fmt)
    except Exception:
        pass  # 某些环境可能不支持
    
    # 3. 设置布局算法
    app.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
    
    # 4. 配置字体平滑和抗锯齿（通过全局字体设置）
    try:
        from PySide6.QtGui import QFont
        
        # 获取当前全局字体并优化
        font = app.font()
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)  # 优先使用抗锯齿
        font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)  # 完整字体提示
        app.setFont(font)
    except Exception:
        pass  # 容错处理


def set_render_mode(mode: str = 'high') -> None:
    """设置渲染模式.
    
    Args:
        mode: 渲染模式 ('fast', 'balanced', 'quality', 'ultra')
    """
    from hnust_exam.utils.theme import RENDER_QUALITY, Theme
    
    mode_map = {
        'fast': {'ANTIALIASING': False, 'TEXT_ANTIALIASING': False},
        'balanced': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True},
        'quality': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True},
        'ultra': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True},
    }
    
    settings = mode_map.get(mode, mode_map['quality'])
    for key, value in settings.items():
        RENDER_QUALITY[key] = value
    
    # 更新主题渲染质量
    Theme.set_render_quality(mode)


def get_render_settings() -> dict:
    """获取当前渲染设置."""
    from hnust_exam.utils.theme import RENDER_QUALITY, DPI_CONFIG
    
    return {
        **RENDER_QUALITY,
        **DPI_CONFIG,
    }
