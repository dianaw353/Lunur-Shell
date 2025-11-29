from fabric.widgets.box import Box
from fabric.widgets.label import Label

from services import notification_service
from services import NetworkService, Wifi
from services import bluetooth_service
from shared.button_toggle import CommandSwitcher
from shared.buttons import HoverButton
from utils.icons import icons, text_icons
from utils.widget_utils import nerd_font_icon, get_icon


class QuickSettingToggler(CommandSwitcher):
    """A button widget to toggle a command."""

    def __init__(
        self,
        command: str,
        name: str,
        enabled_icon: str,
        disabled_icon: str,
        args="",
        **kwargs,
    ):
        super().__init__(
            command,
            enabled_icon,
            disabled_icon,
            name,
            args=args,
            label=True,
            tooltip=False,
            interval=1000,
            style_classes=["quicksettings-toggler"],
            **kwargs,
        )


class NotificationQuickSetting(HoverButton):
    """A button to toggle the notification."""

    def __init__(self, **kwargs):
        super().__init__(
            name="quicksettings-togglebutton",
            style_classes=["quicksettings-toggler"],
            **kwargs,
        )

        self.notification_label = Label(
            label="Noisy",
        )
        self.notification_icon = nerd_font_icon(
            icon=get_icon(text_icons["notification"]["noisy"]),
            props={"style_classes": ["panel-font-icon"]},
        )

        self.children = Box(
            orientation="h",
            spacing=10,
            style="padding: 5px;",
            children=(
                self.notification_icon,
                self.notification_label,
            ),
        )

        notification_service.connect("dnd", self.toggle_notification)

        self.connect("clicked", self.on_click)

        self.toggle_notification(None, notification_service.dont_disturb)

    def on_click(self, *_):
        """Toggle the notification."""
        notification_service.dont_disturb = not notification_service.dont_disturb

    def toggle_notification(self, _, value: bool, *args):
        """Toggle the notification."""

        if value:
            self.notification_label.set_label("Quiet")
            self.notification_icon.set_label(text_icons["notification"]["silent"])

        else:
            self.notification_label.set_label("Noisy")
            self.notification_icon.set_label(text_icons["notification"]["noisy"])


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
            icon=get_icon(text_icons["wifi"]["off"]),
            props={"style_classes": ["panel-font-icon"]},
        )

        self.children = Box(
            orientation="h",
            spacing=10,
            style="padding: 5px;",
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
        self.wifi_icon.set_label(text_icons["wifi"]["off"])
        self.remove_style_class("active")

    def _set_disabled_state(self):
        """Set UI for WiFi disabled."""
        self.wifi_label.set_label("WiFi Off")
        self.wifi_icon.set_label(text_icons["wifi"]["off"])
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
        self.wifi_label.set_label(ssid)
        self.wifi_icon.set_label(self._get_strength_icon(strength))
        self.add_style_class("active")

    def _get_strength_icon(self, strength: int) -> str:
        """Get the appropriate icon based on signal strength."""
        wifi_icons = text_icons["wifi"]

        if strength >= 80:
            return wifi_icons["excellent"]
        elif strength >= 60:
            return wifi_icons["good"]
        elif strength >= 40:
            return wifi_icons["fair"]
        elif strength >= 20:
            return wifi_icons["weak"]
        else:
            return wifi_icons["none"]


class BluetoothQuickSetting(HoverButton):
    """A button to toggle Bluetooth and display connection status."""

    def __init__(self, **kwargs):
        super().__init__(
            name="quicksettings-togglebutton",
            style_classes=["quicksettings-toggler"],
            **kwargs,
        )

        # Use the existing bluetooth service instance
        self.bluetooth = bluetooth_service

        # Create UI elements
        self.bt_label = Label(
            label="Bluetooth Off",
        )
        self.bt_icon = nerd_font_icon(
            icon=text_icons["bluetooth"]["off"],
            props={"style_classes": ["panel-font-icon"]},
        )

        self.children = Box(
            orientation="h",
            spacing=10,
            style="padding: 5px;",
            children=(
                self.bt_icon,
                self.bt_label,
            ),
        )

        # Connect to bluetooth service signals
        if self.bluetooth:
            self.bluetooth.connect("changed", self.on_bluetooth_changed)

        # Connect click handler
        self.connect("clicked", self.on_click)

        # Initialize state
        self.update_bluetooth_state()

    def on_click(self, *_):
        """Toggle Bluetooth enabled state."""
        if self.bluetooth:
            self.bluetooth.toggle_power()

    def on_bluetooth_changed(self, *_):
        """Handle Bluetooth state changes."""
        self.update_bluetooth_state()

    def update_bluetooth_state(self):
        """Update the widget to reflect current Bluetooth state."""
        if not self.bluetooth:
            self._set_unavailable_state()
            return

        state = self.bluetooth.state

        # Handle adapter not available
        if state in ("absent", "unknown"):
            self._set_unavailable_state()
            return

        # Handle turning on/off states
        if state == "turning-on":
            self._set_turning_on_state()
            return

        if state == "turning-off":
            self._set_turning_off_state()
            return

        if not self.bluetooth.enabled:
            self._set_disabled_state()
            return

        # Bluetooth is enabled, check connection status
        connected_devices = self.bluetooth.connected_devices

        if connected_devices and len(connected_devices) > 0:
            # Get first connected device name
            device = connected_devices[0]
            device_name = getattr(device, "alias", None) or getattr(
                device, "name", "Connected"
            )
            self._set_connected_state(device_name, len(connected_devices))
        else:
            self._set_enabled_not_connected_state()

    def _set_unavailable_state(self):
        """Set UI when Bluetooth is not available."""
        self.bt_label.set_label("No Bluetooth")
        self.bt_icon.set_label(text_icons["bluetooth"]["off"])
        self.remove_style_class("active")

    def _set_disabled_state(self):
        """Set UI for Bluetooth disabled."""
        self.bt_label.set_label("Bluetooth Off")
        self.bt_icon.set_label(text_icons["bluetooth"]["off"])
        self.remove_style_class("active")

    def _set_turning_on_state(self):
        """Set UI for Bluetooth turning on."""
        self.bt_label.set_label("Turning On...")
        self.bt_icon.set_label(text_icons["bluetooth"]["on"])
        self.add_style_class("active")

    def _set_turning_off_state(self):
        """Set UI for Bluetooth turning off."""
        self.bt_label.set_label("Turning Off...")
        self.bt_icon.set_label(text_icons["bluetooth"]["off"])
        self.remove_style_class("active")

    def _set_enabled_not_connected_state(self):
        """Set UI for Bluetooth enabled but not connected."""
        self.bt_label.set_label("Not Connected")
        self.bt_icon.set_label(text_icons["bluetooth"]["on"])
        self.add_style_class("active")

    def _set_connected_state(self, device_name: str, device_count: int = 1):
        """Set UI for Bluetooth connected."""
        if device_count > 1:
            self.bt_label.set_label(f"{device_name} +{device_count - 1}")
        else:
            self.bt_label.set_label(device_name or "Connected")
        self.bt_icon.set_label(text_icons["bluetooth"]["connected"])
        self.add_style_class("active")
