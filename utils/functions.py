import json
import os
import shutil
from functools import lru_cache
from gi.repository import GLib, Gio
from .icons import text_icons
from .thread import run_in_thread
from fabric.utils import (
    cooldown,
    get_relative_path,
    exec_shell_command,
    exec_shell_command_async,
)
import time
from typing import Dict, List, Literal, Optional
from loguru import logger

def ttl_lru_cache(seconds_to_live: int, maxsize: int = 128):
    def wrapper(func):
        @lru_cache(maxsize)
        def inner(__ttl, *args, **kwargs):
            return func(*args, **kwargs)
        return lambda *args, **kwargs: inner(time.time() // seconds_to_live, *args, **kwargs)
    return wrapper

# Function to escape the markup
def parse_markup(text):
    return text.replace("\n", " ")

# Function to exclude keys from a dictionary        )
def exclude_keys(d: Dict, keys_to_exclude: List[str]) -> Dict:
    return {k: v for k, v in d.items() if k not in keys_to_exclude}

# Function to format time in hours and minutes
def format_time(secs: int):
    mm, _ = divmod(secs, 60)
    hh, mm = divmod(mm, 60)
    return "%d h %02d min" % (hh, mm)

# Function to send a notification
@cooldown(1)
def send_notification(
    title: str,
    body: str,
    urgency: Literal["low", "normal", "critical"] = "normal",
    icon: Optional[str] = None,
    app_name: str = "Application",
):
    # Create a notification with the title
    notification = Gio.Notification.new(title)
    notification.set_body(body)

    # Set the urgency level if provided
    if urgency in ["low", "normal", "critical"]:
        notification.set_urgent(urgency)

    # Set the icon if provided
    if icon:
        notification.set_icon(Gio.ThemedIcon.new(icon))

    # Optionally, set the application name
    notification.set_title(app_name)

    application = Gio.Application.get_default()

    # Send the notification to the application
    application.send_notification(None, notification)
    return True

# Merge the parsed data with the default configuration
def merge_defaults(data, defaults):
    if isinstance(defaults, dict) and isinstance(data, dict):
        return {**defaults, **data}
    elif isinstance(defaults, list) and isinstance(data, list):
        return data if data else defaults
    else:
        return data if data is not None else defaults


@run_in_thread
def copy_theme(theme: str):
    destination_file = get_relative_path("../styles/theme.scss")
    source_file = get_relative_path(f"../styles/themes/{theme}.scss")

    if not os.path.exists(source_file):
        logger.warning(
            "Warning: The theme file '{theme}.scss' was not found. Using default theme."  # noqa: E501
        )
        source_file = get_relative_path("../styles/themes/catpuccin-mocha.scss")

    try:
        shutil.copyfile(source_file, destination_file)

    except FileNotFoundError:
        logger.error(
            "Error: The theme file '{source_file}' was not found."
        )
        exit(1)

# Validate the widgets
def validate_widgets(parsed_data, default_config):
    """Validates the widgets defined in the layout configuration.

    Supports regular widgets, module groups (@group:X), and collapsible groups (@collapsible_group:X).

    Args:
        parsed_data (dict): The parsed configuration data
        default_config (dict): The default configuration data

    Raises:
        ValueError: If an invalid widget or group reference is found in the layout
    """
    layout = parsed_data["layout"]

    for section in layout:
        for widget in layout[section]:
            # Module groups
            if widget.startswith("@group:"):
                group_idx = widget.replace("@group:", "", 1)
                if not group_idx.isdigit():
                    raise ValueError(
                        f"Invalid module group index '{group_idx}' in section {section}. Must be a number."
                    )
                idx = int(group_idx)
                groups = parsed_data.get("module_groups", [])
                if not isinstance(groups, list):
                    raise ValueError("module_groups must be a list when using @group references")
                if not (0 <= idx < len(groups)):
                    raise ValueError(f"Module group index {idx} is out of range. Available indices: 0-{len(groups)-1}")
                group = groups[idx]
                if not isinstance(group, dict) or "widgets" not in group:
                    raise ValueError(f"Invalid module group at index {idx}. Must be a dict with 'widgets' array.")
                for group_widget in group["widgets"]:
                    if group_widget not in default_config:
                        raise ValueError(
                            f"Invalid widget '{group_widget}' found in module group {idx}. Please check the widget name."
                        )

            # Collapsible groups
            elif widget.startswith("@collapsible_group:"):
                group_idx = widget.replace("@collapsible_group:", "", 1)
                if not group_idx.isdigit():
                    raise ValueError(
                        f"Invalid collapsible group index '{group_idx}' in section {section}. Must be a number."
                    )
                idx = int(group_idx)
                groups = parsed_data.get("collapsible_groups", [])
                if not isinstance(groups, list):
                    raise ValueError("collapsible_groups must be a list when using @collapsible_group references")
                if not (0 <= idx < len(groups)):
                    raise ValueError(f"Collapsible group index {idx} is out of range. Available indices: 0-{len(groups)-1}")
                group = groups[idx]
                if not isinstance(group, dict) or "widgets" not in group:
                    raise ValueError(f"Invalid collapsible group at index {idx}. Must be a dict with 'widgets' array.")
                for group_widget in group["widgets"]:
                    if group_widget not in default_config:
                        raise ValueError(
                            f"Invalid widget '{group_widget}' found in collapsible group {idx}. Please check the widget name."
                        )

            # Regular widgets
            elif widget not in default_config:
                raise ValueError(
                    f"Invalid widget '{widget}' found in section {section}. Please check the widget name."
                )

@ttl_lru_cache(600, 10)
def get_distro_icon():
    distro_id = GLib.get_os_info("ID")
    return text_icons["distro"].get(distro_id, "")  # Fallback icon

# Function to unique list
def unique_list(lst) -> List:
    return list(set(lst))

# Function to check if an executable exists
@ttl_lru_cache(600, 10)
def executable_exists(executable_name):
    executable_path = shutil.which(executable_name)
    return bool(executable_path)

@run_in_thread
def write_json_file(data: Dict, path: str):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to write json: {e}")


# Function to ensure the file exists
@run_in_thread
def ensure_file(path: str) -> None:
    file = Gio.File.new_for_path(path)
    parent = file.get_parent()

    try:
        if parent and not parent.query_exists(None):
            parent.make_directory_with_parents(None)

        if not file.query_exists(None):
            file.create(Gio.FileCreateFlags.NONE, None)
    except GLib.Error as e:
        print(f"Failed to ensure file '{path}': {e.message}")


## Function to execute a shell command asynchronously
def kill_process(process_name: str):
    exec_shell_command_async(f"pkill {process_name}", lambda *_: None)

# Function to check if an app is running
def is_app_running(app_name: str) -> bool:
    return len(exec_shell_command(f"pidof {app_name}")) != 0

# Function to ensure the directory exists


@run_in_thread
def ensure_directory(path: str) -> None:
    if not GLib.file_test(path, GLib.FileTest.EXISTS):
        try:
            Gio.File.new_for_path(path).make_directory_with_parents(None)
        except GLib.Error as e:
            print(f"Failed to create directory {path}: {e.message}")

# Function to get the percentage of a value
def convert_to_percent(
    current: int | float, max: int | float, is_int=True
) -> int | float:
    if is_int:
        return int((current / max) * 100)
    else:
        return (current / max) * 100

def truncate(string: str, max_length: int = 11) -> str:
    """Truncate string if it exceeds max length."""
    if string != None:
        if len(string) > max_length:
            return string[: max_length - 1] + "…"  # Using ellipsis character
        return string
    else:
        return ""
