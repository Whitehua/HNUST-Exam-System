"""主题数据管理（纯数据，不依赖 GUI 框架）.

包含颜色、字体、渲染质量等全局显示配置。
支持高 DPI 缩放、字体平滑、抗锯齿等高级渲染选项。
"""

from typing import Tuple

# 渲染质量配置
RENDER_QUALITY = {
    # Qt 渲染质量级别 (0-3)
    # 0: 默认，1: 低质量，2: 中等质量，3: 高质量
    'ANTIALIASING': True,          # 启用抗锯齿
    'TEXT_ANTIALIASING': True,     # 文本抗锯齿
    'SMOOTH_PIXMAPS': True,        # 图片平滑
    'HIGH_QUALITY_PAINTING': True, # 高质量绘画
    
    # 字体渲染优化
    'FONT_HINTING': 'AUTO',        # 字体提示：NONE, AUTO, FULL
    'FONT_SUBPIXEL_RENDERING': True,  # 子像素渲染
    'FONT_FORCE_VERTICAL_LAYOUT': False,
}

# 高 DPI 配置
DPI_CONFIG = {
    'ENABLE_HIGH_DPI_SCALING': True,   # 启用高 DPI 自动缩放
    'ALLOW_HIGH_DPI_SCALE_FACTOR': True,  # 允许设置缩放比例
    'PIXEL_RATIO': None,               # 像素比 (None=自动)
}


class Theme:
    _LIGHT = {
        "PRIMARY": "#0078d7", "PRIMARY_HOVER": "#005fa3",
        "ACCENT": "#ff9900", "BG": "#f0f0f0",
        "WHITE": "#ffffff", "TEXT": "#333333", "HINT_BG": "#e6f2ff",
        "HINT_TEXT": "#0066cc",
        "DANGER": "#ff6600", "SUCCESS": "#28a745", "MUTED": "#999999",
        "BORDER": "#e0e0e0", "NAV_ACTIVE": "#cce0ff",
        "NAV_CURRENT": "#0050a0", "NAV_ANSWERED_BG": "#d4edda",
        "NAV_ANSWERED_FG": "#155724", "NAV_MARKED_BG": "#f8d7da",
        "NAV_MARKED_FG": "#a71d2a", "NAV_HEADER_BG": "#e8f0fe",
        "SURFACE": "#f8f9fa", "CARD_BG": "#ffffff",
        "INPUT_BG": "#ffffff", "PROGRESS_BG": "#e0e0e0",
        "KB_HINT_BG": "#f8f8f8",
        "TOOLTIP_BG": "#ffffe0", "TOOLTIP_FG": "#333333",
        "NOTES_BG": "#fafbfc", "ANSWER_BG": "#e6ffe6",
        "WARN_BG": "#fff3cd", "WARN_TEXT": "#856404",
        "WARN_BORDER": "#ffc107", "HEADER_SUB_TEXT": "#bfdbfe",
        "CRASH_BG": "#ffffff", "CRASH_HEADER": "#dc2626",
    }

    _DARK = {
        "PRIMARY": "#4da6ff", "PRIMARY_HOVER": "#3d8adf",
        "ACCENT": "#ffaa33", "BG": "#1e1e1e",
        "WHITE": "#2d2d2d", "TEXT": "#e0e0e0", "HINT_BG": "#1a2a3a",
        "HINT_TEXT": "#66aaff",
        "DANGER": "#ff6644", "SUCCESS": "#44cc66", "MUTED": "#888888",
        "BORDER": "#444444", "NAV_ACTIVE": "#2a3a5a",
        "NAV_CURRENT": "#cc7700", "NAV_ANSWERED_BG": "#1a3a2a",
        "NAV_ANSWERED_FG": "#44cc66", "NAV_MARKED_BG": "#3a1a1a",
        "NAV_MARKED_FG": "#ff6644", "NAV_HEADER_BG": "#1a2a3a",
        "SURFACE": "#2a2a2a", "CARD_BG": "#2d2d2d",
        "INPUT_BG": "#333333", "PROGRESS_BG": "#333333",
        "KB_HINT_BG": "#252525",
        "TOOLTIP_BG": "#3a3a2a", "TOOLTIP_FG": "#e0e0e0",
        "NOTES_BG": "#252525", "ANSWER_BG": "#1a3a2a",
        "WARN_BG": "#3a3020", "WARN_TEXT": "#ffcc66",
        "WARN_BORDER": "#886600", "HEADER_SUB_TEXT": "#d0e8ff",
        "CRASH_BG": "#1e1e1e", "CRASH_HEADER": "#b72626",
    }

    _is_dark: bool = False
    _font_scale: float = 1.0

    # 颜色属性（通过 set_dark_mode 动态设置）
    PRIMARY = "#0078d7"
    PRIMARY_HOVER = "#005fa3"
    ACCENT = "#ff9900"
    BG = "#f0f0f0"
    WHITE = "#ffffff"
    TEXT = "#333333"
    HINT_BG = "#e6f2ff"
    HINT_TEXT = "#0066cc"
    DANGER = "#ff6600"
    SUCCESS = "#28a745"
    MUTED = "#999999"
    BORDER = "#e0e0e0"
    NAV_ACTIVE = "#cce0ff"
    NAV_CURRENT = "#0050a0"
    NAV_ANSWERED_BG = "#d4edda"
    NAV_ANSWERED_FG = "#155724"
    NAV_MARKED_BG = "#f8d7da"
    NAV_MARKED_FG = "#a71d2a"
    NAV_HEADER_BG = "#e8f0fe"
    SURFACE = "#f8f9fa"
    CARD_BG = "#ffffff"
    INPUT_BG = "#ffffff"
    PROGRESS_BG = "#e0e0e0"
    KB_HINT_BG = "#f8f8f8"
    TOOLTIP_BG = "#ffffe0"
    TOOLTIP_FG = "#333333"
    NOTES_BG = "#fafbfc"
    ANSWER_BG = "#e6ffe6"
    WARN_BG = "#fff3cd"
    WARN_TEXT = "#856404"
    WARN_BORDER = "#ffc107"
    HEADER_SUB_TEXT = "#bfdbfe"
    CRASH_BG = "#ffffff"
    CRASH_HEADER = "#dc2626"

    # 字体配置 - 优化版
    # 使用更现代的字体栈，支持中文、英文、数字
    FONT_FAMILY = "微软雅黑"  # 主字体（中文优化）
    
    # 基础字体大小（未缩放）
    BASE_FONT_SIZE = 11
    
    # 字体家族列表（按优先级）
    FONT_STACK = [
        FONT_FAMILY,           # 首选：微软雅黑（中文优化）
        "Segoe UI",            # 备选：Segoe UI（Windows 现代字体）
        "Roboto",              # 备选：Roboto（Google 字体）
        "Helvetica Neue",      # 备选：Helvetica Neue（Mac）
        "Arial",               # 兜底：Arial
        "sans-serif",          # 兜底：通用无衬线字体
    ]
    
    # 不同用途的字体配置 (family, size, weight)
    # weight: Normal(400), Medium(500), SemiBold(600), Bold(700)
    FONT = (FONT_FAMILY, BASE_FONT_SIZE, 400)           # 普通文本
    FONT_MEDIUM = (FONT_FAMILY, BASE_FONT_SIZE, 500)    # 中等字重
    FONT_BOLD = (FONT_FAMILY, BASE_FONT_SIZE, 700)      # 粗体
    
    # 标题字体
    FONT_TITLE = (FONT_FAMILY, 14, 700)     # 大标题
    FONT_SUBTITLE = (FONT_FAMILY, 12, 600)  # 副标题
    
    # 特殊字体
    FONT_HUGE = (FONT_FAMILY, 18, 700)      # 超大标题
    FONT_LARGE = (FONT_FAMILY, 13, 500)     # 大号文本
    FONT_SMALL = (FONT_FAMILY, 10, 400)     # 小号文本
    FONT_TINY = (FONT_FAMILY, 8, 400)       # 超小文本
    FONT_MONO = ("Consolas", 11, 400)       # 等宽字体（代码）

    @classmethod
    def set_dark_mode(cls, enabled: bool) -> None:
        """切换深色/浅色模式."""
        cls._is_dark = enabled
        colors = cls._DARK if enabled else cls._LIGHT
        for k, v in colors.items():
            setattr(cls, k, v)

    @classmethod
    def update_fonts(cls) -> None:
        """根据 _font_scale 更新所有字体大小.
        
        支持动态缩放，同时保持合理的字体层级关系。
        """
        s = cls._font_scale
        
        # 基础文本字体
        size = max(8, int(cls.BASE_FONT_SIZE * s))
        cls.FONT = (cls.FONT_FAMILY, size, 400)
        cls.FONT_MEDIUM = (cls.FONT_FAMILY, size, 500)
        cls.FONT_BOLD = (cls.FONT_FAMILY, size, 700)
        
        # 标题字体（保持层级差异）
        cls.FONT_TITLE = (cls.FONT_FAMILY, max(12, int(14 * s)), 700)
        cls.FONT_SUBTITLE = (cls.FONT_FAMILY, max(10, int(12 * s)), 600)
        
        # 特殊字体
        cls.FONT_HUGE = (cls.FONT_FAMILY, max(16, int(18 * s)), 700)
        cls.FONT_LARGE = (cls.FONT_FAMILY, max(11, int(13 * s)), 500)
        cls.FONT_SMALL = (cls.FONT_FAMILY, max(9, int(10 * s)), 400)
        cls.FONT_TINY = (cls.FONT_FAMILY, max(7, int(8 * s)), 400)
        cls.FONT_MONO = ("Consolas", max(9, int(11 * s)), 400)

    @classmethod
    def get_current_colors(cls) -> dict:
        """获取当前主题的所有颜色."""
        return cls._DARK if cls._is_dark else cls._LIGHT
    
    @classmethod
    def set_render_quality(cls, quality: str = 'high') -> None:
        """设置全局渲染质量.
        
        Args:
            quality: 质量级别 ('low', 'medium', 'high', 'ultra')
        """
        quality_map = {
            'low': {'ANTIALIASING': False, 'TEXT_ANTIALIASING': False,
                    'SMOOTH_PIXMAPS': False, 'HIGH_QUALITY_PAINTING': False},
            'medium': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True,
                       'SMOOTH_PIXMAPS': True, 'HIGH_QUALITY_PAINTING': False},
            'high': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True,
                     'SMOOTH_PIXMAPS': True, 'HIGH_QUALITY_PAINTING': True},
            'ultra': {'ANTIALIASING': True, 'TEXT_ANTIALIASING': True,
                      'SMOOTH_PIXMAPS': True, 'HIGH_QUALITY_PAINTING': True,
                      'FONT_HINTING': 'FULL', 'FONT_SUBPIXEL_RENDERING': True},
        }
        
        settings = quality_map.get(quality, quality_map['high'])
        for key, value in settings.items():
            RENDER_QUALITY[key] = value
    
    @classmethod
    def enable_high_dpi(cls, scale_factor: float | None = None) -> None:
        """启用高 DPI 支持.
        
        Args:
            scale_factor: 缩放因子 (None=自动检测)
        """
        DPI_CONFIG['ENABLE_HIGH_DPI_SCALING'] = True
        DPI_CONFIG['ALLOW_HIGH_DPI_SCALE_FACTOR'] = True
        DPI_CONFIG['PIXEL_RATIO'] = scale_factor
