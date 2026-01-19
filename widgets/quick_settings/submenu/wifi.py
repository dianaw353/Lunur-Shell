# widgets/quick_settings/submenu/wifi.py

from fabric.widgets.box import Box
from fabric.widgets.label import Label
from shared.buttons import HoverButton
from utils.icons import text_icons
from utils.widget_utils import nerd_font_icon
import utils.functions as helpers
from utils.exceptions import NetworkManagerNotFoundError

try:
    from services.network import NetworkService, Wifi
except ImportError:
    raise NetworkManagerNotFoundError()


class WifiQuickSetting(HoverButton):
    """A button to toggle WiFi and display connection status."""

    def __init__(self, **kwargs):
        super().__init__(
            name="quicksettings-togglebutton",
            style_classes=["quicksettings-toggler"],
            **kwargs,
        )

        # Initialize the network service (singleton)
        self.network_service = NetworkService()
        self.wifi: Wifi | None = None

        # Create UI elements
        self.wifi_label = Label(
            label="WiFi Off",
        )
        self.wifi_icon = nerd_font_icon(
            icon=text_icons["wifi"]["disabled"],
            props={"style_classes": ["panel-font-icon"]},
        )

        self.children = Box(
            orientation="h",
            spacing=10,
            children=(
                self.wifi_icon,
                self.wifi_label,
            ),
        )

        # The WiFi device is loaded asynchronously, so we need to wait for it
        # Check if already available
        if self.network_service.wifi_device:
            self._setup_wifi_device(self.network_service.wifi_device)

        # Connect to device-ready signal for when it becomes available
        self.network_service.connect("device-ready", self._on_device_ready)

        # Connect click handler
        self.connect("clicked", self.on_click)

    def _on_device_ready(self, *_):
        """Called when network devices are ready."""
        if self.network_service.wifi_device and not self.wifi:
            self._setup_wifi_device(self.network_service.wifi_device)

    def _setup_wifi_device(self, wifi_device: Wifi):
        """Set up the WiFi device and connect signals."""
        self.wifi = wifi_device

        # Connect to WiFi signals
        # "changed" is emitted on any wifi state change
        self.wifi.connect("changed", self.on_wifi_changed)

        # For property changes, use "notify::property-name" format
        self.wifi.connect("notify::enabled", self.on_wifi_enabled_changed)

        # Update initial state
        self.update_wifi_state()

    def on_click(self, *_):
        """Toggle WiFi enabled state."""
        if self.wifi:
            self.wifi.enabled = not self.wifi.enabled

    def on_wifi_changed(self, *_):
        """Handle WiFi state changes."""
        self.update_wifi_state()

    def on_wifi_enabled_changed(self, *_):
        """Handle WiFi enabled/disabled changes."""
        self.update_wifi_state()

    def update_wifi_state(self):
        """Update the widget to reflect current WiFi state."""
        if not self.wifi:
            self._set_unavailable_state()
            return

        if not self.wifi.enabled:
            self._set_disabled_state()
            return

        # WiFi is enabled, check connection status
        ssid = self.wifi.ssid
        strength = self.wifi.strength
        state = self.wifi.state

        if state == "activated" and ssid and ssid != "Disconnected":
            self._set_connected_state(ssid, strength)
        elif state in (
            "prepare",
            "config",
            "need_auth",
            "ip_config",
            "ip_check",
            "secondaries",
        ):
            self._set_connecting_state()
        else:
            self._set_enabled_not_connected_state()

    def _set_unavailable_state(self):
        """Set UI when WiFi device is not available."""
        self.wifi_label.set_label("No WiFi")
        self.wifi_icon.set_label(text_icons["wifi"]["generic"])
        self.remove_style_class("active")

    def _set_disabled_state(self):
        """Set UI for WiFi disabled."""
        self.wifi_label.set_label("WiFi Off")
        self.wifi_icon.set_label(text_icons["wifi"]["generic"])
        self.remove_style_class("active")

    def _set_enabled_not_connected_state(self):
        """Set UI for WiFi enabled but not connected."""
        self.wifi_label.set_label("Not Connected")
        self.wifi_icon.set_label(text_icons["wifi"]["disconnected"])
        self.add_style_class("active")

    def _set_connecting_state(self):
        """Set UI for WiFi connecting."""
        self.wifi_label.set_label("Connecting...")
        self.wifi_icon.set_label(text_icons["wifi"]["disconnected"])
        self.add_style_class("active")

    def _set_connected_state(self, ssid: str, strength: int):
        """Set UI for WiFi connected."""
        self.wifi_label.set_label(helpers.truncate(ssid))
        self.wifi_icon.set_label(self._get_strength_icon(strength))
        self.add_style_class("active")

    def _get_strength_icon(self, strength: int) -> str:
        """Get the appropriate icon based on signal strength."""
        wifi_icons = text_icons["wifi"]

        if strength >= 80:
            return wifi_icons["strength_4"]
        elif strength >= 60:
            return wifi_icons["strength_3"]
        elif strength >= 40:
            return wifi_icons["strength_2"]
        elif strength >= 20:
            return wifi_icons["strength_1"]
        else:
            return wifi_icons["strength_0"]
