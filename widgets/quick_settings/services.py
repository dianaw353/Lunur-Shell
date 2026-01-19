# widgets/quick_settings/services.py

from gi.repository import GLib
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from services.brightness import Brightness
from services import audio_service, bluetooth_service
from utils import functions as helpers
from utils.icons import icons
from utils.widget_utils import get_audio_icon_name, get_brightness_icon_name
from utils.exceptions import NetworkManagerNotFoundError

try:
    from services.network import NetworkService
except ImportError:
    raise NetworkManagerNotFoundError()


def _update_icon(
    image_widget: Image, icon_name: str, fallback_icon: str, size: int = 16
):
    """Sets the icon on the widget with a fallback if the name is missing."""
    if icon_name:
        image_widget.set_from_icon_name(icon_name, size)
    else:
        image_widget.set_from_icon_name(fallback_icon, size)


class AudioService:
    def __init__(self, config):
        self.audio = audio_service
        self.show_audio_percent = config.get("show_audio_percent")
        self.audio_icon = Image(style_classes="panel-icon")

        # Instantiate directly using the top-level import
        self.audio_percent_label = Label() if self.show_audio_percent else None

    def connect_signals(self):
        self.audio.connect("notify::speaker", self._on_speaker_changed)

    def _on_speaker_changed(self, *_):
        speaker = self.audio.speaker
        if speaker:
            speaker.connect("notify::volume", self._on_volume_changed)
            self.update_audio_icon()

    def _on_volume_changed(self, *_):
        self.update_audio_icon()

    def update_audio_icon(self):
        speaker = self.audio.speaker
        if speaker:
            volume = round(speaker.volume)
            icon_info = get_audio_icon_name(volume, speaker.muted)
            icon_name = icon_info.get("icon", icons["audio"].get("muted", ""))

            _update_icon(self.audio_icon, icon_name, icons["audio"].get("muted", ""))

            if self.show_audio_percent and self.audio_percent_label:
                self.audio_percent_label.set_text(f"{volume}%")


class NetworkServiceWrapper:
    def __init__(self, config):
        self.network = NetworkService()
        self.show_network_name = config.get("show_network_name")

        self.network_icon = Image(style_classes="panel-icon")
        self.network_ssid_label = Label() if self.show_network_name else None

    def connect_signals(self):
        self.network.connect("notify::primary-device", self._on_primary_device_changed)
        self.network.connect("notify::wifi-device", self._on_wifi_device_changed)
        self._connect_network_device_signals()

    def _connect_network_device_signals(self):
        if self.network.wifi_device:
            self.network.wifi_device.connect(
                "notify::signal-strength", self._on_network_device_changed
            )
            self.network.wifi_device.connect(
                "notify::state", self._on_network_device_changed
            )
        if self.network.ethernet_device:
            self.network.ethernet_device.connect(
                "notify::state", self._on_network_device_changed
            )

    def _on_primary_device_changed(self, *_):
        self._connect_network_device_signals()
        self.update_network_icon()

    def _on_wifi_device_changed(self, *_):
        self._connect_network_device_signals()
        self.update_network_icon()

    def _on_network_device_changed(self, *_):
        self.update_network_icon()

    def update_network_icon(self):
        wifi_device = self.network.wifi_device
        eth_device = self.network.ethernet_device
        icon_name = None
        ssid = None

        if wifi_device and getattr(wifi_device, "state", "") in (
            "connected",
            "activated",
        ):
            icon_name = wifi_device.get_icon_name()
            ssid = wifi_device.get_ssid() if self.show_network_name else None
        elif eth_device and getattr(eth_device, "state", "") in (
            "connected",
            "activated",
        ):
            icon_name = eth_device.get_icon_name()
            ssid = None
        else:
            icon_name = icons["network"]["wifi"]["disconnected"]

        _update_icon(
            self.network_icon, icon_name, icons["network"]["wifi"]["disconnected"]
        )

        if self.show_network_name and self.network_ssid_label:
            self.network_ssid_label.set_text(helpers.truncate(ssid))


class BrightnessService:
    def __init__(self, config):
        self.brightness_service = Brightness()
        self.show_brightness_percent = config.get("show_brightness_percent")

        self.brightness_icon = Image(style_classes="panel-icon")
        self.brightness_percent_label = (
            Label() if self.show_brightness_percent else None
        )

    def connect_signals(self):
        self.brightness_service.connect(
            "brightness_changed", self._on_brightness_changed
        )

    def _on_brightness_changed(self, *_):
        self.update_brightness_icon()

    def update_brightness_icon(self):
        try:
            current_brightness = self.brightness_service.screen_brightness
            normalized_brightness = helpers.convert_to_percent(
                current_brightness, self.brightness_service.max_screen
            )
            icon_info = get_brightness_icon_name(normalized_brightness)
            icon_name = icon_info.get("icon", icons["brightness"]["indicator"])
        except Exception:
            icon_name = icons["brightness"]["indicator"]
            normalized_brightness = 0

        _update_icon(self.brightness_icon, icon_name, icons["brightness"]["indicator"])

        if self.show_brightness_percent and self.brightness_percent_label:
            self.brightness_percent_label.set_text(f"{normalized_brightness}%")


class BluetoothService:
    DEVICE_ICON_MAP = {
        "headphones": icons["audio"]["type"]["headset"],
        "headset": icons["audio"]["type"]["headset"],
        "speaker": icons["audio"]["type"]["speaker"],
    }

    def __init__(self, config):
        self.bluetooth = bluetooth_service
        self.bluetooth_icon = Image(style_classes="panel-icon")
        self._bluetooth_poll_id = None
        self.connect_signals()

    def connect_signals(self):
        self.bluetooth.connect("notify::enabled", self.update_bluetooth_icon)
        self.bluetooth.connect("device-added", self.update_bluetooth_icon)
        self.bluetooth.connect("device-removed", self.update_bluetooth_icon)
        self.bluetooth.connect("changed", self.update_bluetooth_icon)

    def update_bluetooth_icon(self, *_):
        if not self.bluetooth.enabled:
            icon_name = icons["bluetooth"]["disabled"]
        else:
            icon_name = icons["bluetooth"]["enabled"]
            for device in self.bluetooth.get_connected_devices():
                dev_type = getattr(device, "type", "").lower()
                if dev_type in self.DEVICE_ICON_MAP:
                    icon_name = self.DEVICE_ICON_MAP[dev_type]
                    break

        _update_icon(self.bluetooth_icon, icon_name, icons["bluetooth"]["disabled"])

    def _start_bluetooth_polling(self):
        self._stop_bluetooth_polling()
        self._bluetooth_poll_id = GLib.timeout_add_seconds(
            5, self.update_bluetooth_icon
        )

    def _stop_bluetooth_polling(self):
        if self._bluetooth_poll_id is not None:
            GLib.source_remove(self._bluetooth_poll_id)
            self._bluetooth_poll_id = None
