import ctypes
import json
import os
import shutil
import subprocess
import time
from functools import lru_cache
from typing import Dict, List, Literal, Optional, Union, Any

from gi.repository import GLib, Gio
from fabric.utils import logger

from fabric.utils import (
    cooldown,
    get_relative_path,
    exec_shell_command_async,
)

from .icons import text_icons
from .thread import run_in_thread
from .exceptions import ExecutableNotFoundError


def set_process_name(name: str):
    """
    Sets the process name using libc prctl.
    This helps the window manager identify the application.
    """
    try:
        libc = ctypes.CDLL("libc.so.6")
        # 15 = PR_SET_NAME
        libc.prctl(15, name.encode("utf-8"), 0, 0, 0)
    except Exception as e:
        logger.warning(f"Failed to set process name: {e}")


def ttl_lru_cache(seconds_to_live: int, maxsize: int = 128):
    """
    Decorator: LRU cache that expires after a set time.
    """

    def wrapper(func):
        @lru_cache(maxsize)
        def inner(__ttl, *args, **kwargs):
            return func(*args, **kwargs)

        return lambda *args, **kwargs: inner(
            time.time() // seconds_to_live, *args, **kwargs
        )

    return wrapper


def toggle_command(command: str, full_command: str) -> bool:
    """
    Function to toggle a shell command.
    Returns True if the command is now running (enabled), False if stopped (disabled).
    """
    if is_app_running(command):
        subprocess.run(f"pkill -f {command}", shell=True, capture_output=True)
        return False
    else:
        subprocess.Popen(
            full_command.split(" "),
            stdin=subprocess.DEVNULL,  # No input stream
            stdout=subprocess.DEVNULL,  # Optionally discard the output
            stderr=subprocess.DEVNULL,  # Optionally discard the error output
            start_new_session=True,  # This prevents the process from being killed
        )
        return True


def is_app_running(app_name: str) -> bool:
    """
    Checks if an application is running using pgrep.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", app_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def kill_process(process_name: str):
    """Kills a process by name asynchronously."""
    exec_shell_command_async(f"pkill -f {process_name}", lambda *_: None)


@ttl_lru_cache(600, 10)
def check_executable_exists(executable_name: str):
    """
    Checks if an executable exists in PATH.
    Raises ExecutableNotFoundError if missing.
    """
    if not shutil.which(executable_name):
        raise ExecutableNotFoundError(executable_name)


@ttl_lru_cache(600, 10)
def executable_exists(executable_name: str) -> bool:
    """Returns True if executable exists in PATH, else False."""
    return bool(shutil.which(executable_name))


@ttl_lru_cache(600, 10)
def get_distro_icon() -> str:
    """Gets the icon for the current Linux distribution."""
    distro_id = GLib.get_os_info("ID")
    return text_icons["distro"].get(distro_id, "")


def parse_markup(text: Optional[str]) -> str:
    """Removes newlines to make text safe for Pango markup labels."""
    return text.replace("\n", " ") if text else ""


def exclude_keys(d: Dict, keys_to_exclude: List[str]) -> Dict:
    """Returns a new dictionary without the specified keys."""
    return {k: v for k, v in d.items() if k not in keys_to_exclude}


def unique_list(lst: List) -> List:
    """Returns a list with unique elements."""
    return list(set(lst))


def merge_defaults(data: Any, defaults: Any) -> Any:
    """Recursively merges configuration data with defaults."""
    if isinstance(defaults, dict) and isinstance(data, dict):
        return {**defaults, **data}
    elif isinstance(defaults, list) and isinstance(data, list):
        return data if data else defaults
    else:
        return data if data is not None else defaults


def format_time(secs: int) -> str:
    """Formats seconds into 'X h Y min'."""
    mm, _ = divmod(secs, 60)
    hh, mm = divmod(mm, 60)
    return f"{hh} h {mm:02d} min"


def convert_to_percent(
    current: Union[int, float], max_val: Union[int, float], is_int: bool = True
) -> Union[int, float]:
    """Calculates percentage safely."""
    if max_val == 0:
        return 0
    val = (current / max_val) * 100
    return int(val) if is_int else val


def truncate(string: Optional[str], max_length: int = 11) -> str:
    """Truncates a string and adds ellipsis if it exceeds max_length."""
    if not string:
        return ""
    if len(string) > max_length:
        return string[: max_length - 1] + "…"
    return string


def copy_theme(theme: str):
    """
    Copies the selected theme SCSS file to the active theme location.
    """
    destination_file = get_relative_path("../styles/theme.scss")
    source_file = get_relative_path(f"../styles/themes/{theme}.scss")

    # Fallback to catppuccin if theme doesn't exist
    if not os.path.exists(source_file):
        logger.warning(
            f"Warning: Theme '{theme}' not found. Defaulting to catpuccin-mocha."
        )
        source_file = get_relative_path("../styles/themes/catpuccin-mocha.scss")

    try:
        shutil.copyfile(source_file, destination_file)
    except Exception as e:
        logger.critical(f"Failed to copy theme file: {e}")
        exit(1)


@run_in_thread
def write_json_file(data: Dict, path: str):
    """Writes a dictionary to a JSON file asynchronously."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to write json to {path}: {e}")


@run_in_thread
def ensure_file(path: str) -> None:
    """Ensures a file exists (creating parent directories if needed)."""
    try:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a"):
                os.utime(path, None)
    except Exception as e:
        logger.error(f"Failed to ensure file '{path}': {e}")


@run_in_thread
def ensure_directory(path: str) -> None:
    """Ensures a directory exists."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")


@cooldown(1)
def send_notification(
    title: str,
    body: str,
    urgency: Literal["low", "normal", "critical"] = "normal",
    icon: Optional[str] = None,
    app_name: str = "Application",
):
    """Sends a desktop notification using GObject."""
    notification = Gio.Notification.new(title)
    notification.set_body(body)

    if urgency in {"low", "normal", "critical"}:
        notification.set_urgent(urgency)

    if icon:
        notification.set_icon(Gio.ThemedIcon.new(icon))

    notification.set_title(app_name)

    app = Gio.Application.get_default()
    if app:
        app.send_notification(None, notification)
        return True
    return False


def validate_widgets(parsed_data: Dict, default_config: Dict):
    """
    Validates the layout configuration for modules and groups.
    Raises ValueError if configuration is invalid.
    """
    layout = parsed_data.get("layout", {})
    module_groups = parsed_data.get("module_groups", [])
    collapsible_groups = parsed_data.get("collapsible_groups", [])

    # Cache checked indices to avoid re-checking in loops
    validated_mods = set()
    validated_cols = set()

    def check_group_validity(groups_list, idx, name, validated_set):
        """Helper to validate group structure and content."""
        if idx in validated_set:
            return

        if not isinstance(groups_list, list):
            raise ValueError(f"{name}s must be a list.")

        if not (0 <= idx < len(groups_list)):
            raise ValueError(
                f"{name} index {idx} out of range (0-{len(groups_list) - 1})."
            )

        group = groups_list[idx]
        if not isinstance(group, dict) or "widgets" not in group:
            raise ValueError(
                f"{name} at index {idx} must be a dict with a 'widgets' list."
            )

        for w in group["widgets"]:
            if w not in default_config:
                raise ValueError(f"Invalid widget '{w}' inside {name} {idx}.")

        validated_set.add(idx)

    for section_name, widgets in layout.items():
        if not isinstance(widgets, list):
            continue

        for widget in widgets:
            # Check Module Groups
            if widget.startswith("@group:"):
                try:
                    idx = int(widget[7:])
                    check_group_validity(
                        module_groups, idx, "Module group", validated_mods
                    )
                except ValueError:
                    raise ValueError(
                        f"Invalid module group syntax: {widget} in {section_name}"
                    )

            # Check Collapsible Groups
            elif widget.startswith("@collapsible_group:"):
                try:
                    idx = int(widget[19:])
                    check_group_validity(
                        collapsible_groups, idx, "Collapsible group", validated_cols
                    )
                except ValueError:
                    raise ValueError(
                        f"Invalid collapsible group syntax: {widget} in {section_name}"
                    )

            # Check Standard Widgets
            elif widget not in default_config:
                raise ValueError(
                    f"Invalid widget '{widget}' found in section '{section_name}'. "
                    "Check spelling or config."
                )
