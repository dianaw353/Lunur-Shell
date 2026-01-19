from gi.repository import GLib
from fabric.utils import exec_shell_command_async
from shared.widget_container import ButtonWidget
from utils.icons import icons
from utils.widget_utils import get_icon
from utils.exceptions import ExecutableNotFoundError
import utils.functions as helpers
from shared.dbus_helper import GioDBusHelper

# Power profile options
power_profiles = ["balanced", "performance", "power-saver"]


class PowerProfileButton(ButtonWidget):
    _profile_icons = {}

    def __init__(self, widget_config: dict, **kwargs):
        super().__init__(
            config=widget_config["power_profiles"],
            name="power-profile-button",
            **kwargs,
        )

        if not helpers.executable_exists("powerprofilesctl"):
            raise ExecutableNotFoundError("powerprofilesctl")

        # Initialize with a default profile
        self.current_profile = "balanced"
        self.icon_widget = None

        # Cache icons if not already
        if not PowerProfileButton._profile_icons:
            for profile in power_profiles:
                PowerProfileButton._profile_icons[profile] = get_icon(
                    icons.get("powerprofiles", {}).get(
                        profile, "dialog-question-symbolic"
                    ),
                    size=self.config.get("icon_size", 20),
                )

        # Set initial icon
        self.icon_widget = PowerProfileButton._profile_icons[self.current_profile]
        self.box.add(self.icon_widget)
        self.icon_widget.show()
        self.set_tooltip_text(f"Power Profile: {self.current_profile.capitalize()}")
        self.box.show_all()

        # Update actual profile asynchronously
        GLib.idle_add(self.update_profile_display)

        # Connect click and DBus listener
        self.connect("clicked", self.on_click)
        self.init_dbus_listener()

    def get_current_profile(self, callback):
        """Fetch current profile asynchronously and call callback(profile)"""

        def inner(output):
            profile = output.strip()
            if profile not in power_profiles:
                profile = "balanced"
            callback(profile)

        exec_shell_command_async("powerprofilesctl get", inner)

    def update_profile_display(self):
        """Update widget display asynchronously"""

        def apply_profile(profile):
            if profile == self.current_profile:
                return
            self.current_profile = profile

            if self.icon_widget:
                self.box.remove(self.icon_widget)
            self.icon_widget = PowerProfileButton._profile_icons.get(profile)
            self.box.add(self.icon_widget)
            self.icon_widget.show()
            self.set_tooltip_text(f"Power Profile: {profile.capitalize()}")
            self.box.show_all()

        self.get_current_profile(apply_profile)

    def on_click(self, button):
        next_profile = self.get_next_profile()
        self.set_power_profile(next_profile)

    def get_next_profile(self):
        idx = (
            power_profiles.index(self.current_profile)
            if self.current_profile in power_profiles
            else 0
        )
        return power_profiles[(idx + 1) % len(power_profiles)]

    def set_power_profile(self, profile):
        if profile not in power_profiles:
            return
        try:
            exec_shell_command_async(f"powerprofilesctl set {profile}")
        except Exception:
            pass

    def init_dbus_listener(self):
        """Listen for DBus signals from powerprofiles daemon"""

        def on_properties_changed(
            connection,
            sender_name,
            object_path,
            interface_name,
            signal_name,
            parameters,
        ):
            iface, changed_props, _ = parameters.unpack()
            if "ActiveProfile" in changed_props:
                GLib.idle_add(self.update_profile_display)

        dbus = GioDBusHelper(
            bus_name="net.hadess.PowerProfiles",
            object_path="/net/hadess/PowerProfiles",
            interface_name="net.hadess.PowerProfiles",
        )
        dbus.listen_signal(
            sender="net.hadess.PowerProfiles",
            interface_name="org.freedesktop.DBus.Properties",
            member="PropertiesChanged",
            object_path="/net/hadess/PowerProfiles",
            callback=on_properties_changed,
        )
