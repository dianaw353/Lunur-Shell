# widgets/quick_settings/submenu/__init__.py

from .wifi import WifiQuickSetting
from .bluetooth import BluetoothQuickSetting
from .hyprsunset import HyprSunsetSubMenu, HyprSunsetToggle

__all__ = [
    "WifiQuickSetting",
    "BluetoothQuickSetting",
    "HyprSunsetSubMenu",
    "HyprSunsetToggle",
]
