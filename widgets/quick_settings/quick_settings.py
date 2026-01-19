import time
from fabric.utils import logger
from fabric.widgets.box import Box
from utils.widget_settings import BarConfig
from shared.widget_container import ButtonWidget
from .services import (
    AudioService,
    NetworkServiceWrapper,
    BrightnessService,
    BluetoothService,
)
from .quick_settings_menu import QuickSettingsMenu


class QuickSettings:
    def __init__(self, config, debug=False):
        self.debug = debug

        # Audio
        t_start = time.perf_counter()
        self.audio_service = AudioService(config)
        self.audio_service.connect_signals()
        if self.debug:
            logger.info(
                f"  [QS] Audio Service: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Network
        t_start = time.perf_counter()
        self.network_service = NetworkServiceWrapper(config)
        self.network_service.connect_signals()
        if self.debug:
            logger.info(
                f"  [QS] Network Service: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Brightness
        t_start = time.perf_counter()
        self.brightness_service = BrightnessService(config)
        self.brightness_service.connect_signals()
        if self.debug:
            logger.info(
                f"  [QS] Brightness Service: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Bluetooth
        t_start = time.perf_counter()
        self.bluetooth_service = BluetoothService(config)
        self.bluetooth_service._start_bluetooth_polling()
        if self.debug:
            logger.info(
                f"  [QS] Bluetooth Service: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

    def get_icons_and_labels(self, bar_icons):
        icons_map = {
            "audio": self.audio_service.audio_icon,
            "network": self.network_service.network_icon,
            "brightness": self.brightness_service.brightness_icon,
            "bluetooth": self.bluetooth_service.bluetooth_icon,
        }
        ordered_icons = []
        for name in bar_icons:
            if name in icons_map:
                ordered_icons.append(icons_map[name])
                if name == "network" and self.network_service.network_ssid_label:
                    ordered_icons.append(self.network_service.network_ssid_label)
                elif name == "audio" and self.audio_service.audio_percent_label:
                    ordered_icons.append(self.audio_service.audio_percent_label)
                elif (
                    name == "brightness"
                    and self.brightness_service.brightness_percent_label
                ):
                    ordered_icons.append(
                        self.brightness_service.brightness_percent_label
                    )
        return ordered_icons

    def update_all_icons(self):
        self.audio_service.update_audio_icon()
        self.network_service.update_network_icon()
        self.brightness_service.update_brightness_icon()
        self.bluetooth_service.update_bluetooth_icon()


class QuickSettingsButtonWidget(ButtonWidget):
    def __init__(self, widget_config: BarConfig, **kwargs):
        # Extract debug flag safely
        self.debug = widget_config.get("general", {}).get("debug", False)

        super().__init__(
            widget_config["quick_settings"], name="quick_settings", **kwargs
        )
        self.popup = None
        self.connect("clicked", self.show_popover)

        self.config = widget_config["quick_settings"]

        # Measure Services Init
        t_start = time.perf_counter()
        self.services = QuickSettings(self.config, debug=self.debug)
        if self.debug:
            logger.info(
                f"[QS] Services Init Total: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Measure Icon/Label Generation
        t_start = time.perf_counter()
        bar_icons = self.config.get("bar_icons")
        ordered_icons = self.services.get_icons_and_labels(bar_icons)
        self.children = Box(spacing=4, children=ordered_icons)
        if self.debug:
            logger.info(
                f"[QS] UI Generation: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Measure Signal Connections
        t_start = time.perf_counter()
        self.connect_signals(bar_icons)
        if self.debug:
            logger.info(
                f"[QS] Signal Connections: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

        # Measure Initial Updates
        t_start = time.perf_counter()
        self.update_initial_icons(bar_icons)
        if self.debug:
            logger.info(
                f"[QS] Initial Icon Updates: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

    def show_popover(self, *_):
        if self.popup:
            self.popup.destroy()

        # Optional: Measure popover open time
        t_start = time.perf_counter()
        self.popup = QuickSettingsMenu(point_to_widget=self, config=self.config)
        self.popup.open()
        if self.debug:
            logger.info(
                f"[QS] Popover Open: {(time.perf_counter() - t_start) * 1000:.1f}ms"
            )

    def connect_signals(self, bar_icons):
        if "audio" in bar_icons:
            self.services.audio_service.connect_signals()
        if "brightness" in bar_icons:
            self.services.brightness_service.connect_signals()
        if "network" in bar_icons:
            self.services.network_service.connect_signals()
        if "bluetooth" in bar_icons:
            self.services.bluetooth_service.connect_signals()
            self.services.bluetooth_service._start_bluetooth_polling()

    def update_initial_icons(self, bar_icons):
        if "network" in bar_icons:
            self.services.network_service.update_network_icon()
        if "audio" in bar_icons:
            self.services.audio_service.update_audio_icon()
        if "brightness" in bar_icons:
            self.services.brightness_service.update_brightness_icon()
        if "bluetooth" in bar_icons:
            self.services.bluetooth_service.update_bluetooth_icon()
