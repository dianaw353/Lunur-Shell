from typing import Any, List, Literal

import gi
from fabric.core.service import Property, Service, Signal
from fabric.utils import bulk_connect, exec_shell_command_async
from gi.repository import Gio
from typing import Callable
from utils.exceptions import NetworkManagerNotFoundError

try:
    gi.require_version("NM", "1.0")
    from gi.repository import NM
except ValueError:
    raise NetworkManagerNotFoundError()


class Wifi(Service):
    """A service to manage wifi devices"""

    @Signal
    def changed(self) -> None: ...

    @Signal
    def enabled(self) -> bool: ...

    @Signal
    def scanning(self, is_scanning: bool) -> None: ...

    def __init__(self, client: NM.Client, device: NM.DeviceWifi, **kwargs):
        self._client: NM.Client = client
        self._device: NM.DeviceWifi = device
        self._ap: NM.AccessPoint | None = None
        self._ap_signal: int | None = None
        self._is_scanning: bool = False
        super().__init__(**kwargs)

        self._client.connect(
            "notify::wireless-enabled",
            lambda *args: self.notifier("enabled", args),
        )
        if self._device:
            bulk_connect(
                self._device,
                {
                    "notify::active-access-point": self._activate_ap,
                    "access-point-added": lambda *args: self.emit("changed"),
                    "access-point-removed": lambda *args: self.emit("changed"),
                    "state-changed": self.ap_update,
                },
            )
            self._activate_ap()

    def ap_update(self, *_):
        self.emit("changed")
        for sn in [
            "enabled",
            "internet",
            "strength",
            "frequency",
            "access-points",
            "ssid",
            "state",
            "icon-name",
        ]:
            self.notify(sn)

    def _activate_ap(self, *_):
        if self._ap:
            self._ap.disconnect(self._ap_signal)
        self._ap = self._device.get_active_access_point()
        if not self._ap:
            return

        self._ap_signal = self._ap.connect(
            "notify::strength", lambda *args: self.ap_update()
        )  # type: ignore

    def toggle_wifi(self):
        self._client.wireless_set_enabled(not self._client.wireless_get_enabled())

    def scan(self):
        """Start scanning for WiFi networks and emit scanning signal"""
        if self._device and not self._is_scanning:
            self._is_scanning = True
            self.emit("scanning", True)
            self._device.request_scan_async(
                None,
                self._on_scan_finished,
            )

    def _on_scan_finished(self, device, result):
        """Callback when scan finishes."""
        try:
            device.request_scan_finish(result)
        except Exception:
            pass
        self._is_scanning = False
        self.emit("scanning", False)
        self.emit("changed")

    def disconnect_network(self):
        """Disconnect from the current WiFi network."""
        if self._device:
            self._device.disconnect_async(
                None,
                self._on_disconnect_finished,
            )

    def _on_disconnect_finished(self, device, result):
        """Callback when disconnect finishes."""
        try:
            device.disconnect_finish(result)
        except Exception:
            pass
        self.emit("changed")

    def notifier(self, name: str, *args):
        self.notify(name)
        self.emit("changed")
        return

    @Property(bool, "read-write", default_value=False)
    def enabled(self) -> bool:  # noqa: F811
        return bool(self._client.wireless_get_enabled())

    @enabled.setter
    def enabled(self, value: bool):
        self._client.wireless_set_enabled(value)

    @Property(int, "readable")
    def strength(self):
        return self._ap.get_strength() if self._ap else -1

    @Property(str, "readable")
    def icon_name(self):
        if not self._ap:
            return "network-wireless-disabled-symbolic"

        if self.internet == "activated":
            return {
                80: "network-wireless-signal-excellent-symbolic",
                60: "network-wireless-signal-good-symbolic",
                40: "network-wireless-signal-ok-symbolic",
                20: "network-wireless-signal-weak-symbolic",
                00: "network-wireless-signal-none-symbolic",
            }.get(
                min(80, 20 * round(self._ap.get_strength() / 20)),
                "network-wireless-no-route-symbolic",
            )
        if self.internet == "activating":
            return "network-wireless-acquiring-symbolic"

        return "network-wireless-offline-symbolic"

    @Property(int, "readable")
    def frequency(self):
        return self._ap.get_frequency() if self._ap else -1

    @Property(str, "readable")
    def internet(self):
        active_conn = self._device.get_active_connection()
        if not active_conn:
            return "disconnected"

        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            active_conn.get_state(),
            "unknown",
        )

    @Property(object, "readable")
    def access_points(self) -> List[object]:
        points: list[NM.AccessPoint] = self._device.get_access_points()

        def make_ap_dict(ap: NM.AccessPoint):
            try:
                wpa_flags = ap.get_wpa_flags()
                rsn_flags = ap.get_rsn_flags()
                security_none = getattr(NM, "80211ApSecurityFlags").NONE
                # Check if network has any security flags
                is_secured = bool(
                    wpa_flags != security_none or rsn_flags != security_none
                )
            except Exception:
                is_secured = True

            return {
                "bssid": ap.get_bssid(),
                "last_seen": ap.get_last_seen(),
                "ssid": (
                    NM.utils_ssid_to_utf8(ap.get_ssid().get_data())
                    if ap.get_ssid()
                    else "Unknown"
                ),
                "active-ap": self._ap,
                "strength": ap.get_strength(),
                "frequency": ap.get_frequency(),
                "secured": is_secured,
                "icon-name": {
                    80: "network-wireless-signal-excellent-symbolic",
                    60: "network-wireless-signal-good-symbolic",
                    40: "network-wireless-signal-ok-symbolic",
                    20: "network-wireless-signal-weak-symbolic",
                    00: "network-wireless-signal-none-symbolic",
                }.get(
                    min(80, 20 * round(ap.get_strength() / 20)),
                    "network-wireless-no-route-symbolic",
                ),
            }

        return list(map(make_ap_dict, points))

    @Property(str, "readable")
    def ssid(self):
        if not self._ap:
            return "Disconnected"
        ssid = self._ap.get_ssid().get_data()
        return NM.utils_ssid_to_utf8(ssid) if ssid else "Unknown"

    @Property(str, "readable")
    def state(self):
        return {
            NM.DeviceState.UNMANAGED: "unmanaged",
            NM.DeviceState.UNAVAILABLE: "unavailable",
            NM.DeviceState.DISCONNECTED: "disconnected",
            NM.DeviceState.PREPARE: "prepare",
            NM.DeviceState.CONFIG: "config",
            NM.DeviceState.NEED_AUTH: "need_auth",
            NM.DeviceState.IP_CONFIG: "ip_config",
            NM.DeviceState.IP_CHECK: "ip_check",
            NM.DeviceState.SECONDARIES: "secondaries",
            NM.DeviceState.ACTIVATED: "activated",
            NM.DeviceState.DEACTIVATING: "deactivating",
            NM.DeviceState.FAILED: "failed",
        }.get(self._device.get_state(), "unknown")


class Ethernet(Service):
    """A service to manage ethernet devices"""

    @Signal
    def changed(self) -> None: ...

    @Signal
    def enabled(self) -> bool: ...

    @Property(int, "readable")
    def speed(self) -> int:
        return self._device.get_speed()

    @Property(str, "readable")
    def internet(self) -> str:
        active_conn = self._device.get_active_connection()
        if not active_conn:
            return "disconnected"

        return {
            NM.ActiveConnectionState.ACTIVATED: "activated",
            NM.ActiveConnectionState.ACTIVATING: "activating",
            NM.ActiveConnectionState.DEACTIVATING: "deactivating",
            NM.ActiveConnectionState.DEACTIVATED: "deactivated",
        }.get(
            active_conn.get_state(),
            "disconnected",
        )

    @Property(str, "readable")
    def icon_name(self) -> str:
        network = self.internet
        if network == "activated":
            return "network-wired-symbolic"

        elif network == "activating":
            return "network-wired-acquiring-symbolic"

        elif self._device.get_connectivity != NM.ConnectivityState.FULL:
            return "network-wired-no-route-symbolic"

        return "network-wired-disconnected-symbolic"

    def __init__(self, client: NM.Client, device: NM.DeviceEthernet, **kwargs) -> None:
        super().__init__(**kwargs)
        self._client: NM.Client = client
        self._device: NM.DeviceEthernet = device

        for names in (
            "active-connection",
            "icon-name",
            "internet",
            "speed",
            "state",
        ):
            self._device.connect(f"notify::{names}", lambda *_: self.notifier(names))

        self._device.connect("notify::speed", lambda *_: print(_))

    def notifier(self, names):
        self.notify(names)
        self.emit("changed")


class NetworkService(Service):
    """A service to manage network devices"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(NetworkService, cls).__new__(cls)
        return cls._instance

    @Signal
    def device_ready(self) -> None: ...

    def __init__(self, **kwargs):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

        self._client: NM.Client | None = None
        self.wifi_device: Wifi | None = None
        self.ethernet_device: Ethernet | None = None
        super().__init__(**kwargs)
        NM.Client.new_async(
            cancellable=None,
            callback=self._init_network_client,
        )

    def _init_network_client(self, client: NM.Client, task: Gio.Task, **kwargs):
        self._client = client
        wifi_device: NM.DeviceWifi | None = self._get_device(NM.DeviceType.WIFI)  # type: ignore
        ethernet_device: NM.DeviceEthernet | None = self._get_device(
            NM.DeviceType.ETHERNET
        )

        if wifi_device:
            self.wifi_device = Wifi(self._client, wifi_device)
            self.emit("device-ready")

        if ethernet_device:
            self.ethernet_device = Ethernet(client=self._client, device=ethernet_device)
            self.emit("device-ready")

        self.notify("primary-device")

    def _get_device(self, device_type) -> Any:
        devices: List[NM.Device] = self._client.get_devices()  # type: ignore
        return next(
            (x for x in devices if x.get_device_type() == device_type),
            None,
        )

    def _get_primary_device(self) -> Literal["wifi", "wired"] | None:
        if not self._client:
            return None

        primary_conn = self._client.get_primary_connection()
        if primary_conn is None:
            return "wifi"

        conn_type = str(primary_conn.get_connection_type())

        if "wireless" in conn_type:
            return "wifi"
        elif "ethernet" in conn_type:
            return "wired"

        return None

    def connect_wifi_bssid(self, bssid: str):
        """Connect to a WiFi network by BSSID (for saved/open networks)."""
        exec_shell_command_async(
            f"nmcli device wifi connect {bssid}",
            lambda *args: None,
        )

    def connect_wifi_with_password(
        self,
        bssid: str,
        ssid: str,
        password: str,
        callback: Callable[[bool, str | None], None] | None = None,
    ):
        """Connect to a WiFi network with a password.

        Args:
            bssid: The BSSID of the access point
            ssid: The SSID (network name) for the connection profile
            password: The WiFi password
            callback: Optional callback(success: bool, error: str | None)
        """
        # Escape special characters in password for shell
        escaped_password = password.replace("'", "'\\''")

        command = f"nmcli device wifi connect '{bssid}' password '{escaped_password}'"

        def on_complete(result: str, *args):
            if callback:
                # Check if connection was successful
                if (
                    "successfully activated" in result.lower()
                    or "successfully" in result.lower()
                ):
                    callback(True, None)
                else:
                    callback(False, result if result else "Connection failed")

        exec_shell_command_async(command, on_complete)

    def get_saved_connections(self) -> List[str]:
        """Get list of saved WiFi connection SSIDs."""
        if not self._client:
            return []

        saved_ssids = []
        connections = self._client.get_connections()

        for conn in connections:
            settings = conn.get_setting_wireless()
            if settings:
                ssid_bytes = settings.get_ssid()
                if ssid_bytes:
                    ssid = ssid_bytes.get_data().decode("utf-8", errors="ignore")
                    saved_ssids.append(ssid)

        return saved_ssids

    def has_saved_connection(self, ssid: str) -> bool:
        """Check if a WiFi network has saved credentials."""
        return ssid in self.get_saved_connections()

    def forget_wifi_network(
        self, ssid: str, callback: Callable[[bool], None] | None = None
    ):
        """Delete a saved WiFi connection profile.

        Args:
            ssid: The SSID of the network to forget
            callback: Optional callback(success: bool)
        """
        escaped_ssid = ssid.replace("'", "'\\''")
        command = f"nmcli connection delete '{escaped_ssid}'"

        def on_complete(result: str, *args):
            if callback:
                callback(
                    "successfully deleted" in result.lower()
                    or "deleted" in result.lower()
                )

        exec_shell_command_async(command, on_complete)

    @Property(str, "readable")
    def primary_device(self) -> str:
        res = self._get_primary_device()
        return res if res is not None else "unknown"
