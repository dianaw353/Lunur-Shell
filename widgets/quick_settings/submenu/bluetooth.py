import gi
from fabric.bluetooth.service import BluetoothClient, BluetoothDevice
from fabric.utils import bulk_connect
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gtk

from services import bluetooth_service
from shared.buttons import HoverButton, QSChevronButton, ScanButton
from shared.list import ListBox
from shared.separator import Separator
from shared.submenu import QuickSubMenu
from utils.icons import text_icons
from utils.widget_utils import nerd_font_icon

gi.require_versions({"Gtk": "3.0"})


class BluetoothDeviceBox(CenterBox):
    """A widget to display a Bluetooth device in a box."""

    def __init__(self, device: BluetoothDevice, **kwargs):
        super().__init__(
            spacing=2,
            style_classes=["submenu-button"],
            h_expand=True,
            name="bluetooth-device-box",
            **kwargs,
        )
        self.device: BluetoothDevice = device

        self.icon_to_text_icon = {
            "audio-headset": text_icons["ui"]["headset"],
            "phone": text_icons["ui"]["phone"],
            "audio-headphones": text_icons["ui"]["headphones"],
            "keyboard": text_icons["ui"]["keyboard"],
            "mouse": text_icons["ui"]["mouse"],
            "audio-speakers": text_icons["ui"]["speakers"],
            "camera": text_icons["ui"]["camera"],
            "printer": text_icons["ui"]["printer"],
            "tv": text_icons["ui"]["tv"],
            "watch": text_icons["ui"]["watch"],
            "bluetooth": text_icons["bluetooth"]["on"],
        }

        self.connect_button = HoverButton(
            style_classes=["wifi-auth-button", "wifi-connect-button"]
        )
        self.connect_button.connect(
            "clicked",
            lambda _: self.device.set_property("connecting", not self.device.connected),
        )

        # Store signal IDs to disconnect them later
        self._signal_ids = bulk_connect(
            self.device,
            {
                "notify::connecting": self.on_device_connecting,
                "notify::connected": self.on_device_connect,
            },
        )
        self.connect("destroy", self._on_destroy)

        device_name = device.name or "Unknown Device"

        self.add_start(
            nerd_font_icon(
                icon=self.icon_to_text_icon.get(
                    device.icon_name, text_icons["bluetooth"]["on"]
                ),
                props={"style_classes": ["panel-font-icon"]},
            ),
        )

        self.add_start(
            Label(
                label=device_name,
                style_classes=["submenu-item-label"],
                ellipsization="end",
            )
        )

        self.add_end(self.connect_button)

        self.on_device_connect()

    def _on_destroy(self, *_):
        """Clean up signals when widget is destroyed to prevent crashes."""
        if self.device and self._signal_ids:
            for signal_id in self._signal_ids:
                try:
                    if self.device.handler_is_connected(signal_id):
                        self.device.disconnect(signal_id)
                except Exception:
                    pass
            self._signal_ids = ()

    def on_device_connecting(self, *_):
        if self.device.connecting:
            self.connect_button.set_label("Connecting...")
        elif self.device.connected is False:
            self.connect_button.set_label("Failed to connect")

    def on_device_connect(self, *_):
        self.connect_button.set_label(
            "Disconnect" if self.device.connected else "Connect"
        )


class BluetoothSubMenu(QuickSubMenu):
    """A submenu to display the Bluetooth settings."""

    def __init__(self, **kwargs):
        self.client = bluetooth_service

        self.separator = Separator(
            orientation="horizontal",
            style_classes=["app-volume-separator"],
        )
        self.paired_devices_listbox = ListBox(
            visible=True, name="paired-devices-listbox"
        )
        self.paired_devices_container = Box(
            orientation="v",
            spacing=10,
            h_expand=True,
            children=[
                Label(
                    label="Paired Devices",
                    h_align="start",
                    style_classes=["panel-text"],
                ),
                self.paired_devices_listbox,
            ],
        )

        self.available_devices_listbox = ListBox(
            visible=True, name="available-devices-listbox"
        )
        self.available_devices_container = Box(
            orientation="v",
            spacing=4,
            h_expand=True,
            children=[
                Label(
                    label="Available Devices",
                    h_align="start",
                    name="available-devices-label",
                    style_classes=["panel-text"],
                ),
                self.available_devices_listbox,
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
                    self.paired_devices_container,
                    self.available_devices_container,
                ],
                spacing=10,
            ),
        )

        super().__init__(
            title="Bluetooth",
            title_icon=text_icons["bluetooth"]["on"],
            scan_button=self.scan_button,
            child=self.child,
            **kwargs,
        )

        # Connect device-added signal
        self._added_signal_id = self.client.connect(
            "device-added", self.populate_new_device
        )

        # Connect to self for cleanup
        self.connect("destroy", self._on_destroy)

        # Track device rows for easy update
        self.device_rows = {}
        # Track device signals separately
        self.device_signals = {}

        # Populate initial devices
        for device in self.client.devices:
            self.add_device_row(device)
            # Track this signal connection
            sig_id = device.connect("notify::paired", self.on_device_paired_changed)
            self.device_signals[device.address] = (device, sig_id)

    def _on_destroy(self, *_):
        """Clean up submenu signals."""
        if self._added_signal_id:
            try:
                self.client.disconnect(self._added_signal_id)
            except Exception:
                pass

        # Clean up device specific signals
        for device, sig_id in self.device_signals.values():
            try:
                if device.handler_is_connected(sig_id):
                    device.disconnect(sig_id)
            except Exception:
                pass
        self.device_signals.clear()

    def on_scan_toggle(self, btn: Button):
        """Toggle Bluetooth scanning - this is the ONLY place scanning starts."""
        self.client.toggle_scan()
        if self.client.scanning:
            btn.add_style_class("active")
        else:
            btn.remove_style_class("active")
        self.scan_button.play_animation()

    def populate_new_device(self, client: BluetoothClient, address: str):
        device = client.get_device(address)
        if device is None:
            return

        # Avoid duplicate connections
        if address not in self.device_signals:
            self.add_device_row(device)
            sig_id = device.connect("notify::paired", self.on_device_paired_changed)
            self.device_signals[address] = (device, sig_id)

    def add_device_row(self, device: BluetoothDevice):
        # Remove existing row if present
        if device.address in self.device_rows:
            row, listbox = self.device_rows[device.address]
            listbox.remove(row)
            row.destroy()

        bt_item = Gtk.ListBoxRow(visible=True, name="bluetooth-device-row")
        bt_item.add(BluetoothDeviceBox(device))
        if device.paired:
            self.paired_devices_listbox.add(bt_item)
            self.device_rows[device.address] = (bt_item, self.paired_devices_listbox)
        else:
            self.available_devices_listbox.add(bt_item)
            self.device_rows[device.address] = (
                bt_item,
                self.available_devices_listbox,
            )

    def on_device_paired_changed(self, device, *_):
        # Move device row between listboxes when paired status changes
        self.add_device_row(device)


class BluetoothToggle(QSChevronButton):
    """A widget to display the Bluetooth status."""

    def __init__(self, submenu: QuickSubMenu, **kwargs):
        super().__init__(
            style_classes=["quicksettings-toggler"],
            action_label="On",
            action_icon=text_icons["bluetooth"]["on"],
            submenu=submenu,
            **kwargs,
        )

        # Client Signals
        self.client = bluetooth_service
        self._device_signals = []  # Store device signal IDs

        # Track main client signals
        self._client_signals = bulk_connect(
            self.client,
            {"device-added": self.new_device, "notify::enabled": self.toggle_bluetooth},
        )
        self.connect("destroy", self._on_destroy)

        self.toggle_bluetooth(self.client)

        for device in self.client.devices:
            self.new_device(self.client, device.address)
        if self.client.connected_devices:
            self.device_connected(self.client.connected_devices[0])

        # Button Signals
        self.connect("action-clicked", lambda *_: self.client.toggle_power())

    def _on_destroy(self, *_):
        # Disconnect client signals
        for sig_id in self._client_signals:
            try:
                self.client.disconnect(sig_id)
            except Exception:
                pass

        # Disconnect individual device signals
        for device, sig_id in self._device_signals:
            try:
                if device.handler_is_connected(sig_id):
                    device.disconnect(sig_id)
            except Exception:
                pass
        self._device_signals.clear()

    def toggle_bluetooth(self, client: BluetoothClient, *_):
        if client.enabled:
            self.add_style_class("active")
            self.action_icon.set_label(text_icons["bluetooth"]["on"])
            self.action_label.set_label("On")
        else:
            self.remove_style_class("active")
            self.action_icon.set_label(text_icons["bluetooth"]["off"])
            self.action_label.set_label("Off")

    def new_device(self, client: BluetoothClient, address: str):
        device = client.get_device(address)
        if device is None:
            return

        # Track the connected signal
        sig_id = device.connect("changed", self.device_connected)
        self._device_signals.append((device, sig_id))

    def device_connected(self, device: BluetoothDevice, *_):
        # Safety check if widget is destroyed but signal fired
        try:
            if not self.action_label or self.action_label.in_destruction():
                return
        except AttributeError:
            return

        if device.connected:
            self.action_label.set_label(device.name)
        elif self.action_label.get_label() == device.name:
            self.action_label.set_label(
                self.client.connected_devices[0].name
                if self.client.connected_devices
                else "On"
            )
