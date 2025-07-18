from datetime import datetime

from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import GdkPixbuf, GLib, Gtk

from services import BatteryService
from shared import ButtonWidget
from utils import BarConfig
from utils.functions import format_time, send_notification
from utils.icons import icons


class BatteryWidget(ButtonWidget):
    """A widget to display the current battery status."""

    def __init__(self, widget_config: BarConfig, **kwargs):
        super().__init__(
            widget_config["battery"],
            name="battery",
            **kwargs,
        )

        self.full_battery_level = self.config["full_battery_level"]
        self.battery_label = Label(
            label="100%", style_classes="panel-text", visible=False
        )
        self.battery_icon = Image(
            icon_name=icons["battery"]["full"],
            icon_size=self.config["icon_size"],
        )

        self.client = BatteryService()
        self.client.connect("changed", self.update_ui)
        self.time_since_last_notification = datetime.now()

        notif_cfg = widget_config.get("notifications", {})
        self.notification_timeout = notif_cfg.get("timeout", 3000)

        self.update_ui()

    def update_ui(self, *_):
        is_present = self.client.get_property("IsPresent") == 1
        battery_percent = (
            round(self.client.get_property("Percentage")) if is_present else 0
        )
        battery_state = self.client.get_property("State")
        is_charging = battery_state == 1 if is_present else False

        time_since_last_notification = (
            datetime.now() - self.time_since_last_notification
        ).total_seconds()

        if (
            time_since_last_notification > self.notification_timeout
            and battery_percent == self.full_battery_level
            and self.config["notifications"]["full_battery"]
        ):
            print("Battery is full and notification is enabled")
            timeout_id = GLib.timeout_add(
                5000,
                lambda: (
                    send_notification(
                        title="Battery Full",
                        body="Battery is fully charged.",
                        urgency="normal",
                        icon=icons["battery"]["full-charging"],
                        app_name="Battery",
                    ),
                    GLib.source_remove(timeout_id),
                ),
            )
            self.time_since_last_notification = datetime.now()

        temperature = self.client.get_property("Temperature")
        energy = self.client.get_property("Energy")
        time_remaining = (
            self.client.get_property("TimeToFull")
            if is_charging
            else self.client.get_property("TimeToEmpty")
        )

        self.battery_label.set_text(f" {battery_percent}%")

        self.battery_icon.set_from_icon_name(
            self.client.get_property("IconName"), self.config["icon_size"]
        )

        if self.config["orientation"] == "horizontal":
            pixbuf = Gtk.IconTheme.get_default().load_icon(
                self.client.get_property("IconName"),
                14,
                Gtk.IconLookupFlags.FORCE_SIZE,
            )
            rotated_pixbuf = pixbuf.rotate_simple(GdkPixbuf.PixbufRotation.CLOCKWISE)
            self.battery_icon.set_from_pixbuf(rotated_pixbuf)

        self.box.children = (self.battery_icon, self.battery_label)

        if self.config["label"]:
            self.battery_label.set_visible(True)

            if (
                self.config["hide_label_when_full"]
                and battery_percent == self.full_battery_level
            ):
                self.battery_label.hide()

        if self.config["tooltip"]:
            status_text = (
                "󱠴 Status: Charging" if is_charging else "󱠴 Status: Discharging"
            )
            tool_tip_text = (
                f"󱐋 Energy : {round(energy, 2)} Wh\n Temperature: {temperature}°C"
            )
            formatted_time = format_time(time_remaining)
            if battery_percent == self.full_battery_level:
                self.set_tooltip_text(
                    f"{status_text}\n󰄉 Time to full: 0\n{tool_tip_text}"
                )
            elif is_charging and battery_percent < self.full_battery_level:
                self.set_tooltip_text(
                    f"{status_text}\n󰄉 Time to full: {formatted_time}\n{tool_tip_text}"
                )
            else:
                self.set_tooltip_text(
                    f"{status_text}\n󰄉 Time to empty: {formatted_time}\n{tool_tip_text}"
                )

        return True
