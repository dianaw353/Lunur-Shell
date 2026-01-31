import gi
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from fabric.widgets.revealer import Revealer
from gi.repository import Gtk, GLib
from typing import Any, Dict, List, cast, Callable

from shared.buttons import HoverButton, QSChevronButton, ScanButton
from shared.list import ListBox
from shared.separator import Separator
from shared.submenu import QuickSubMenu
from utils.icons import text_icons, icons
import utils.functions as helpers
from utils.exceptions import NetworkManagerNotFoundError
from utils.widget_utils import nerd_font_icon

try:
    from services.network import NetworkService, Wifi
except ImportError:
    raise NetworkManagerNotFoundError()

gi.require_versions({"Gtk": "3.0"})


class PasswordEntry(Box):
    def __init__(
        self, on_submit: Callable[[str], None], on_cancel: Callable[[], None], **kwargs
    ):
        super().__init__(
            orientation="v",
            spacing=8,
            style_classes=["wifi-password-container"],
            h_expand=True,
            **kwargs,
        )

        self._on_submit = on_submit
        self._on_cancel = on_cancel
        self._is_visible = False

        self.entry = Entry(
            placeholder="Enter password...",
            visibility=False,
            h_expand=True,
            style_classes=["wifi-password-entry"],
        )
        self.entry.connect("activate", self._handle_entry_activate)
        self.entry.connect("changed", self._on_entry_changed)

        self.visibility_button = Button(
            style_classes=["wifi-visibility-button"],
            h_align="center",
            v_align="center",
        )
        self._update_visibility_icon()
        self.visibility_button.connect("clicked", self._toggle_visibility)

        entry_row = Box(
            orientation="h",
            spacing=4,
            h_expand=True,
            style_classes=["wifi-entry-row"],
            children=[self.entry, self.visibility_button],
        )

        self.cancel_button = HoverButton(
            label="Cancel",
            style_classes=["wifi-auth-button", "wifi-cancel-button"],
        )
        self.cancel_button.connect("clicked", self._handle_cancel)

        self.connect_button = HoverButton(
            label="Connect",
            style_classes=["wifi-auth-button", "wifi-connect-button"],
            sensitive=False,  # Disabled until password is entered
        )
        self.connect_button.connect("clicked", self._handle_connect)

        button_row = Box(
            orientation="h",
            spacing=8,
            h_align="end",
            children=[self.cancel_button, self.connect_button],
        )

        self.add(entry_row)
        self.add(button_row)

    def _update_visibility_icon(self):
        icon_name = (
            icons["ui"].get("eye", "view-conceal-symbolic")
            if self._is_visible
            else icons["ui"].get("eye-off", "view-reveal-symbolic")
        )

        # Clear existing children
        for child in self.visibility_button.get_children():
            self.visibility_button.remove(child)

        self.visibility_button.add(
            Image(
                icon_name=icon_name,
                icon_size=16,
            )
        )
        self.visibility_button.show_all()

    def _toggle_visibility(self, *_):
        self._is_visible = not self._is_visible
        self.entry.set_visibility(self._is_visible)
        self._update_visibility_icon()

    def _on_entry_changed(self, entry):
        text = entry.get_text()
        # WPA passwords must be at least 8 characters
        self.connect_button.set_sensitive(len(text) >= 8)

    def _handle_entry_activate(self, *_):
        if len(self.entry.get_text()) >= 8:
            self._handle_connect()

    def _handle_connect(self, *_):
        password = self.entry.get_text()
        if password and len(password) >= 8:
            self._on_submit(password)

    def _handle_cancel(self, *_):
        self.clear()
        self._on_cancel()

    def focus_entry(self):
        self.entry.grab_focus()
        return False  # For GLib.idle_add compatibility

    def clear(self):
        self.entry.set_text("")
        self._is_visible = False
        self.entry.set_visibility(False)
        self._update_visibility_icon()
        self.connect_button.set_sensitive(False)


class WifiNetworkBox(Box):
    """A widget representing a single WiFi network in the list with inline auth."""

    def __init__(
        self,
        network: dict,
        wifi: Wifi,
        network_service: NetworkService,
        is_active: bool = False,
        **kwargs,
    ):
        super().__init__(
            orientation="v",
            spacing=0,
            h_expand=True,
            name="wifi-network-box-container",
            **kwargs,
        )

        self.network = network
        self.wifi = wifi
        self.network_service = network_service
        self.is_active = is_active
        self.bssid = network.get("bssid", "")
        self.ssid = network.get("ssid", "Unknown")
        self.strength = network.get("strength", 0)
        self.is_secured = network.get("secured", False)
        self._is_connecting = False

        # Main network info row
        self.network_row = CenterBox(
            spacing=2,
            style_classes=["submenu-button"],
            h_expand=True,
        )

        self.connect_button = HoverButton(
            style_classes=["wifi-auth-button", "wifi-connect-button"]
        )
        self._setup_button_state()

        strength_icon = self._get_strength_icon(self.strength)

        network_info_box = Box(
            orientation="h",
            spacing=8,
            h_expand=True,
        )

        network_info_box.add(
            nerd_font_icon(
                icon=strength_icon,
                props={"style_classes": ["panel-font-icon"]},
            )
        )

        if self.is_secured:
            lock_icon = Image(
                icon_name=icons["ui"]["lock"],
                icon_size=16,
                style_classes=["wifi-lock-icon"],
                h_align="start",
                visible=True,
            )
            network_info_box.add(lock_icon)

        network_info_box.add(
            Label(
                label=self.ssid,
                style_classes=["submenu-item-label"],
                ellipsization="end",
                h_expand=True,
                h_align="start",
            )
        )

        self.network_row.add_start(network_info_box)
        self.network_row.add_end(self.connect_button)

        self.password_entry = PasswordEntry(
            on_submit=self._on_password_submitted,
            on_cancel=self._on_auth_cancelled,
        )

        self.auth_revealer = Revealer(
            transition_type="slide-down",
            transition_duration=200,
            child=self.password_entry,
            reveal_child=False,
        )

        # Add both to the vertical container
        self.add(self.network_row)
        self.add(self.auth_revealer)

    def _setup_button_state(self):
        if self.is_active:
            self.connect_button.set_label("Disconnect")
            self.connect_button.connect("clicked", self._on_disconnect_clicked)
        else:
            self.connect_button.set_label("Connect")
            self.connect_button.connect("clicked", self._on_connect_clicked)

    def _on_connect_clicked(self, *_):
        if self._is_connecting:
            return

        if self.is_secured:
            if self.network_service.has_saved_connection(self.ssid):
                self._connect_with_saved_credentials()
            else:
                # Need password - show auth dialog
                self._show_auth_dialog()
        else:
            self._connect_open_network()

    def _show_auth_dialog(self):
        self.password_entry.clear()
        self.auth_revealer.set_reveal_child(True)
        GLib.timeout_add(250, self.password_entry.focus_entry)

    def _hide_auth_dialog(self):
        self.auth_revealer.set_reveal_child(False)
        self.password_entry.clear()

    def _on_password_submitted(self, password: str):
        self._hide_auth_dialog()
        self.connect_with_password(password)

    def _on_auth_cancelled(self):
        self._hide_auth_dialog()

    def _connect_with_saved_credentials(self):
        self._set_connecting_state()
        self.network_service.connect_wifi_bssid(self.bssid)

    def _connect_open_network(self):
        self._set_connecting_state()
        self.network_service.connect_wifi_bssid(self.bssid)

    def connect_with_password(self, password: str):
        self._set_connecting_state()
        self.network_service.connect_wifi_with_password(
            bssid=self.bssid,
            ssid=self.ssid,
            password=password,
            callback=self._on_connection_result,
        )

    def _set_connecting_state(self):
        self._is_connecting = True
        self.connect_button.set_label("Connecting...")
        self.connect_button.set_sensitive(False)

    def _on_connection_result(self, success: bool, error: str | None):
        self._is_connecting = False
        self.connect_button.set_sensitive(True)

        if success:
            self.connect_button.set_label("Connected")
        else:
            self.connect_button.set_label("Connect")
            print(f"WiFi connection failed: {error}")

    def reset_state(self):
        self._is_connecting = False
        self.connect_button.set_label("Connect")
        self.connect_button.set_sensitive(True)
        self._hide_auth_dialog()

    def _on_disconnect_clicked(self, *_):
        self.connect_button.set_label("Disconnecting...")
        self.connect_button.set_sensitive(False)
        self.wifi.disconnect_network()

    def _get_strength_icon(self, strength: int) -> str:
        wifi_icons = text_icons["wifi"]
        if strength >= 80:
            return wifi_icons["strength_4"]
        if strength >= 60:
            return wifi_icons["strength_3"]
        if strength >= 40:
            return wifi_icons["strength_2"]
        if strength >= 20:
            return wifi_icons["strength_1"]
        return wifi_icons["strength_0"]


class WifiSubMenu(QuickSubMenu):
    """A submenu to display WiFi settings and network list."""

    def __init__(self, **kwargs):
        self.network_service = NetworkService()
        self.wifi: Wifi | None = None
        self._wifi_signals: List[int] = []
        self.network_rows: Dict[str, tuple] = {}

        self.separator = Separator(
            orientation="horizontal",
            style_classes=["app-volume-separator"],
        )

        # Connected network container
        self.connected_network_listbox = ListBox(
            visible=True, name="connected-network-listbox"
        )
        self.connected_network_container = Box(
            orientation="v",
            spacing=10,
            h_expand=True,
            children=[
                Label(
                    label="Connected",
                    h_align="start",
                    style_classes=["panel-text"],
                ),
                self.connected_network_listbox,
            ],
        )

        self.available_networks_listbox = ListBox(
            visible=True, name="available-networks-listbox"
        )
        self.available_networks_container = Box(
            orientation="v",
            spacing=4,
            h_expand=True,
            children=[
                Label(
                    label="Available Networks",
                    h_align="start",
                    name="available-networks-label",
                    style_classes=["panel-text"],
                ),
                self.available_networks_listbox,
            ],
        )

        self.scan_button = ScanButton()
        self.scan_button.connect("clicked", self.on_scan_toggle)

        self.child = ScrolledWindow(
            min_content_size=(-1, 190),
            max_content_size=(-1, 190),
            propagate_width=True,
            propagate_height=True,
            child=Box(
                orientation="v",
                children=[
                    self.separator,
                    self.connected_network_container,
                    self.available_networks_container,
                ],
                spacing=10,
            ),
        )

        super().__init__(
            title="Wi-Fi",
            title_icon=text_icons["wifi"]["strength_4"],
            scan_button=self.scan_button,
            child=self.child,
            **kwargs,
        )

        self._device_ready_signal = self.network_service.connect(
            "device-ready", self._on_device_ready
        )
        self.connect("destroy", self._on_destroy)

        if self.network_service.wifi_device:
            self._setup_wifi_device(self.network_service.wifi_device)

    def _on_destroy(self, *_):
        """Clean up signals when widget is destroyed."""
        try:
            self.network_service.disconnect(self._device_ready_signal)
        except Exception:
            pass

        if self.wifi:
            for sig_id in self._wifi_signals:
                try:
                    if self.wifi.handler_is_connected(sig_id):
                        self.wifi.disconnect(sig_id)
                except Exception:
                    pass
        self._wifi_signals.clear()

    def _on_device_ready(self, *_):
        if self.network_service.wifi_device and not self.wifi:
            self._setup_wifi_device(self.network_service.wifi_device)

    def _setup_wifi_device(self, wifi_device: Wifi):
        self.wifi = wifi_device
        self._wifi_signals = [
            self.wifi.connect("changed", self._on_wifi_changed),
            self.wifi.connect("notify::enabled", self._on_wifi_enabled_changed),
            self.wifi.connect("scanning", self._on_scanning_changed),
        ]
        self._update_header_state()
        self._populate_networks()

    def _on_wifi_changed(self, *_):
        self._update_header_state()
        self._populate_networks()

    def _on_wifi_enabled_changed(self, *_):
        self._update_header_state()
        self._populate_networks()

    def _on_scanning_changed(self, wifi, is_scanning: bool):
        """Handle scanning state changes."""
        if is_scanning:
            self.scan_button.add_style_class("active")
        else:
            self.scan_button.remove_style_class("active")

    def on_scan_toggle(self, btn: Button):
        """Start WiFi scanning."""
        if self.wifi and self.wifi.enabled:
            self.wifi.scan()
            self.scan_button.play_animation()

    def _populate_networks(self):
        """Populate the network lists."""
        self._clear_listbox(self.connected_network_listbox)
        self._clear_listbox(self.available_networks_listbox)
        self.network_rows.clear()

        if not self.wifi or not self.wifi.enabled:
            self.connected_network_container.set_visible(False)
            self.available_networks_container.set_visible(False)
            return

        access_points = cast(List[Dict[str, Any]], self.wifi.access_points)
        current_ssid = self.wifi.ssid
        is_connected = self.wifi.state == "activated"

        sorted_aps = sorted(
            access_points, key=lambda x: x.get("strength", 0), reverse=True
        )

        # Track SSIDs we've already added to avoid duplicates
        seen_ssids: set[str] = set()
        connected_added = False
        available_count = 0

        for ap in sorted_aps:
            ssid = ap.get("ssid", "Unknown")
            if not ssid or ssid == "Unknown" or ssid in seen_ssids:
                continue

            seen_ssids.add(ssid)
            is_active = ssid == current_ssid and is_connected

            network_row = Gtk.ListBoxRow(visible=True, name="wifi-network-row")

            network_box = WifiNetworkBox(
                network=ap,
                wifi=self.wifi,
                network_service=self.network_service,
                is_active=is_active,
            )

            network_row.add(network_box)

            if is_active:
                self.connected_network_listbox.add(network_row)
                connected_added = True
            else:
                self.available_networks_listbox.add(network_row)
                available_count += 1

            self.network_rows[ssid] = (network_row, is_active)

        self.connected_network_container.set_visible(connected_added)
        self.available_networks_container.set_visible(available_count > 0)

    def _clear_listbox(self, listbox: ListBox):
        for child in listbox.get_children():
            listbox.remove(child)
            child.destroy()

    def _update_header_state(self):
        """Update the header label based on connection state."""
        if not hasattr(self, "title_label"):
            return

        if not self.wifi or not self.wifi.enabled:
            self.title_label.set_label("Wi-Fi")
            return

        if (
            self.wifi.state == "activated"
            and self.wifi.ssid
            and self.wifi.ssid != "Disconnected"
        ):
            self.title_label.set_label(helpers.truncate(self.wifi.ssid, max_length=20))
        else:
            self.title_label.set_label("Wi-Fi")


class WifiToggle(QSChevronButton):
    """A widget to display the WiFi status with submenu."""

    def __init__(self, submenu: QuickSubMenu, **kwargs):
        super().__init__(
            style_classes=["quicksettings-toggler"],
            action_label="WiFi Off",
            action_icon=text_icons["wifi"]["disabled"],
            submenu=submenu,
            **kwargs,
        )

        self.network_service = NetworkService()
        self.wifi: Wifi | None = None
        self._wifi_signals: List[int] = []

        self._device_ready_signal = self.network_service.connect(
            "device-ready", self._on_toggle_device_ready
        )
        self.connect("destroy", self._on_toggle_destroy)

        if self.network_service.wifi_device:
            self._setup_wifi_device(self.network_service.wifi_device)

        self.connect("action-clicked", lambda *_: self._toggle_wifi())

    def _on_toggle_destroy(self, *_):
        """Clean up signals when widget is destroyed."""
        try:
            self.network_service.disconnect(self._device_ready_signal)
        except Exception:
            pass

        if self.wifi:
            for sig_id in self._wifi_signals:
                try:
                    if self.wifi.handler_is_connected(sig_id):
                        self.wifi.disconnect(sig_id)
                except Exception:
                    pass
        self._wifi_signals.clear()

    def _on_toggle_device_ready(self, *_):
        if self.network_service.wifi_device and not self.wifi:
            self._setup_wifi_device(self.network_service.wifi_device)

    def _setup_wifi_device(self, wifi_device: Wifi):
        self.wifi = wifi_device
        self._wifi_signals = [
            self.wifi.connect("changed", self._on_toggle_wifi_changed),
            self.wifi.connect("notify::enabled", self._on_toggle_wifi_enabled_changed),
        ]
        self._update_state()

    def _toggle_wifi(self):
        if self.wifi:
            self.wifi.enabled = not self.wifi.enabled

    def _on_toggle_wifi_changed(self, *_):
        self._update_state()

    def _on_toggle_wifi_enabled_changed(self, *_):
        self._update_state()

    def _update_state(self):
        if not self.wifi:
            self._set_unavailable_state()
            return

        if not self.wifi.enabled:
            self._set_disabled_state()
            return

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
        self.action_label.set_label("No WiFi")
        self.action_icon.set_label(text_icons["wifi"]["generic"])
        self.remove_style_class("active")

    def _set_disabled_state(self):
        self.action_label.set_label("WiFi Off")
        self.action_icon.set_label(text_icons["wifi"]["disabled"])
        self.remove_style_class("active")

    def _set_enabled_not_connected_state(self):
        self.action_label.set_label("Not Connected")
        self.action_icon.set_label(text_icons["wifi"]["disconnected"])
        self.add_style_class("active")

    def _set_connecting_state(self):
        self.action_label.set_label("Connecting...")
        self.action_icon.set_label(text_icons["wifi"]["disconnected"])
        self.add_style_class("active")

    def _set_connected_state(self, ssid: str, strength: int):
        self.action_label.set_label(helpers.truncate(ssid))
        self.action_icon.set_label(self._get_strength_icon(strength))
        self.add_style_class("active")

    def _get_strength_icon(self, strength: int) -> str:
        wifi_icons = text_icons["wifi"]
        if strength >= 80:
            return wifi_icons["strength_4"]
        if strength >= 60:
            return wifi_icons["strength_3"]
        if strength >= 40:
            return wifi_icons["strength_2"]
        if strength >= 20:
            return wifi_icons["strength_1"]
        return wifi_icons["strength_0"]
