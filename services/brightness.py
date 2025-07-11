import os

from fabric.core.service import Property, Service, Signal
from fabric.utils import exec_shell_command_async, monitor_file
from gi.repository import GLib
from loguru import logger

import utils.functions as helpers


@helpers.run_in_thread
def exec_brightnessctl_async(args: str):
    exec_shell_command_async(f"brightnessctl {args}", lambda _: None)


# Discover screen backlight device
try:
    screen_device = os.listdir("/sys/class/backlight")
    screen_device = screen_device[0] if screen_device else ""
except FileNotFoundError:
    logger.error("No backlight devices found")
    screen_device = ""

# Discover keyboard backlight device
try:
    kbd = os.listdir("/sys/class/leds")
    kbd = [x for x in kbd if "kbd_backlight" in x]
    kbd = kbd[0] if kbd else ""
except FileNotFoundError:
    logger.error("No keyboard backlight devices found")
    kbd = ""


class Brightness(Service):
    """Service to manage screen brightness levels."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Brightness, cls).__new__(cls)
        return cls._instance

    @Signal
    def brightness_changed(self, value: int) -> None:
        """Signal emitted when screen brightness changes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if not helpers.executable_exists("brightnessctl"):
            logger.error("Command brightnessctl not found")

        self.screen_backlight_path = f"/sys/class/backlight/{screen_device}"
        self.max_screen = self.do_read_max_brightness(self.screen_backlight_path)

        if screen_device == "":
            return

        self.screen_monitor = monitor_file(f"{self.screen_backlight_path}/brightness")
        self.screen_monitor.connect(
            "changed",
            lambda _, file, *args: self.emit(
                "brightness_changed",
                round(int(file.load_bytes()[0].get_data())),
            ),
        )

        logger.info(f"Brightness service initialized for device: {screen_device}")

    def do_read_max_brightness(self, path: str) -> int:
        max_brightness_path = os.path.join(path, "max_brightness")
        if os.path.exists(max_brightness_path):
            with open(max_brightness_path) as f:
                return int(f.readline())
        return -1

    @Property(int, "read-write")
    def screen_brightness(self) -> int:
        brightness_path = os.path.join(self.screen_backlight_path, "brightness")
        if os.path.exists(brightness_path):
            with open(brightness_path) as f:
                return int(f.readline())
        logger.warning(f"Brightness file does not exist: {brightness_path}")
        return -1

    @screen_brightness.setter
    def screen_brightness(self, value: int):
        if not (0 <= value <= self.max_screen):
            value = max(0, min(value, self.max_screen))

        try:
            exec_brightnessctl_async(f"--device '{screen_device}' set {value}")
            self.emit("brightness_changed", int((value / self.max_screen) * 100))
            logger.info(
                f"Set screen brightness to {value} (out of {self.max_screen})"
            )
        except GLib.Error as e:
            logger.error(f"Error setting screen brightness: {e.message}")
        except Exception as e:
            logger.exception(f"Unexpected error setting screen brightness: {e}")

    @Property(int, "read-write")
    def keyboard_brightness(self) -> int:  # type: ignore
        with open(self.kbd_backlight_path + "/brightness") as f:
            brightness = int(f.readline())
        return brightness

    @keyboard_brightness.setter
    def keyboard_brightness(self, value):
        if value < 0 or value > self.max_kbd:
            return
        try:
            exec_brightnessctl_async(f"--device '{kbd}' set {value}")
        except GLib.Error as e:
            logger.exception(e.message)
