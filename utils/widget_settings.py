from typing import TypedDict, List, Dict

from .types import Anchor, Layer

# Common configuration fields that will be reused
BaseConfig = TypedDict("BaseConfig", {"label": bool, "tooltip": bool})

DateTimeMenu = TypedDict(
    "DateTimeMenu",
    {
        "clock_format": str,
        "format": str,
    },
)

# ScreenCorners configuration
ScreenCorners = TypedDict(
    "ScreenCorners",
    {
        "enabled": bool,
        "size": int,
    },
)

# Bar configuration
General = TypedDict(
    "General",
    {
        "screen_corners": ScreenCorners,
        "location": str,
        "layer": Layer,
    },
)

AppLauncher = TypedDict(
    "AppLauncher",
    {
        "icon_size": int,
        "app_icon_size": int,
        "show_descriptions": bool,  
    },
)

Workspaces = TypedDict(
    "Workspaces",
    {
        "count": int,
        "hide_unoccupied": bool,
        "ignored": List[int],
        "reverse_scroll": bool,
        "empty_scroll": bool,
        "default_label_format": str,
        "icon_map": Dict[str, str],
    },
)


# Notification configuration
Notification = TypedDict(
    "Notification",
    {
        "enabled": bool,
        "ignored": List[str],
        "timeout": int,
        "anchor": Anchor,
        "auto_dismiss": bool,
        "play_sound": bool,
        "sound_file": str,
        "max_count": int,
        "dismiss_on_hover": bool,
        "max_actions": int,
        "per_app_limits": Dict[str, int],
    },
)

Battery = TypedDict(
    "Battery",
    {
        "label": bool,
        "tooltip": bool,
        "orientation": str,
        "full_battery_level": int,
        "hide_label_when_full": bool,
        "icon_size": int,
        "notifications": TypedDict(
            "BatteryNotifications",
            {
                "enabled": bool,
                "full_battery": bool,
                "charging": bool,
                "low_battery": bool,
                "low_threshold": int,
            },
        ),
    },
)

# SystemTray configuration
SystemTray = TypedDict("SystemTray", {**BaseConfig.__annotations__, "transition_duration": int, "icon_size": int, "slide_direction": str})

# Quick Settings
QuickSettings = TypedDict(
    "QuickSettings",
    {
        "bar_icons": List[str],
        "show_ssid": bool,
        "show_audio_percent": bool,
        "show_brightness_percent": bool,
    },
)

Keybinds = TypedDict(
    "Keybinds",
    {
        "enabled": bool,
        "path": str, 
    },
)

# WindowTitle configuration
WindowTitle = TypedDict(
    "WindowTitle",
    {
        "icon": bool,
        "truncation": bool,
        "truncation_size": int,
        "hide_when_zero": bool,
        "title_map": List[Dict[str, str]],
    },
)

PowerProfiles = TypedDict(
    "PowerProfiles",
    {
        "icon_size": int,
    }
)

Hyprpicker = TypedDict(
    "Hyprpicker",
    {
        "icon_size": int,
        "tooltip": bool,
    }
)

Cliphist = TypedDict("Cliphist", {"icon": str, **BaseConfig.__annotations__})


# Playerctl configuration
Playerctl = TypedDict("Playerctl", {**BaseConfig.__annotations__, "transition_duration": int, "icon_size": int, "slide_direction": str})

EmojiPicker = TypedDict(
    "emoji_picker",
    {"icon": str, **BaseConfig.__annotations__, "per_row": int, "per_column": int},
)

# Theme configuration
Theme = TypedDict("Theme", {"name": str})


# Collapsible group
CollapsibleGroup = TypedDict(
    "CollapsibleGroup",
    {
        "widgets": List[str],
        "spacing": int,
        "style_classes": List[str],
        "collapsed_icon": str,
        "slide_direction": str,
        "transition_duration": int,
    },
)

# Power menu buttons
Sleep = TypedDict("SleepButtonConfig", {**BaseConfig.__annotations__})
Reboot = TypedDict("RebootButtonConfig", {**BaseConfig.__annotations__})
Logout = TypedDict("LogoutButtonConfig", {**BaseConfig.__annotations__})
Shutdown = TypedDict("ShutdownButtonConfig", {**BaseConfig.__annotations__})

# Recording configuration
Recording = TypedDict(
    "Recording", {"path": str, "icon_size": int, "tooltip": bool, "audio": bool}
)

Screenshot = TypedDict(
    "Screenshot",
    {
        "icon": str,
        "path": str,
        **BaseConfig.__annotations__,
        "annotation": bool,
        # "capture_sound": bool,
    }
)

# OSD configuration
OSD = TypedDict(
    "OSD",
    {
        "osds": List[str],
        "enabled": bool,
        "anchor": str,
        "icon_size": int,
        # "opacity": int,
        "timeout": int,
        "transition_type": str,
        "transition_duration": int,
        "percentage": bool,
        "orientation": str,
    },
)
    
# Main minimal BarConfig for your current widgets
class BarConfig(TypedDict):
    date_time: DateTimeMenu
    workspaces: Workspaces
    notifications: Notification
    battery: Battery
    system_tray: SystemTray
    quick_settings: QuickSettings
    general: General
    app_launcher: AppLauncher
    keybinds: Keybinds
    theme: Theme
    window_title: WindowTitle
    hyprpicker: Hyprpicker
    power_profiles: PowerProfiles
    cliphist: Cliphist
    playerctl: Playerctl
    collapsible_groups: List[CollapsibleGroup]
    sleep: Sleep
    reboot: Reboot
    logout: Logout
    shutdown: Shutdown
    screenshot: Screenshot
    recorder: Recording
    osd: OSD 
