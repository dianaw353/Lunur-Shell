from datetime import datetime

from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import GdkPixbuf, GLib, Gio, Gtk

from services.battery import BatteryService
from shared.widget_container import ButtonWidget
from utils.widget_settings import BarConfig
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

        self.last_percentage = None
        self.last_charging_state = None
        self.low_battery_notified = False
        self.full_battery_notified = False
        self.charging_notified = False
        self.discharging_notified = False
        self.initialized = False

        self.update_ui()

    def _can_send_notifications(self):
        return Gio.Application.get_default() is not None

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
            and self.config.get("notifications", {}).get("full_battery")
        ):

            def notify_full_battery():
                if self._can_send_notifications():
                    send_notification(
                        title="Battery Full",
                        body="Battery is fully charged.",
                        urgency="normal",
                        icon=icons["battery"].get("full-charging", ""),
                        app_name="Battery",
                    )
                return False  # Remove timeout

            GLib.timeout_add(5000, notify_full_battery)
            self.time_since_last_notification = datetime.now()

        temperature = self.client.get_property("Temperature") or 0
        energy = self.client.get_property("Energy") or 0
        time_remaining = (
            self.client.get_property("TimeToFull")
            if is_charging
            else self.client.get_property("TimeToEmpty")
        ) or 0

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
                self.config.get("hide_label_when_full")
                and battery_percent == self.full_battery_level
            ):
                self.battery_label.hide()

        if self.config.get("tooltip"):
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
            elif is_charging:
                self.set_tooltip_text(
                    f"{status_text}\n󰄉 Time to full: {formatted_time}\n{tool_tip_text}"
                )
            else:
                self.set_tooltip_text(
                    f"{status_text}\n󰄉 Time to empty: {formatted_time}\n{tool_tip_text}"
                )

        if self.initialized:
            self._check_notifications(battery_percent, is_charging)

        self.last_percentage = battery_percent
        self.last_charging_state = is_charging
        self.initialized = True

        return True

    def _check_notifications(self, percentage, is_charging):
        notifications = self.config.get("notifications", {})
        if self.last_charging_state is None:
            return

        is_full = percentage >= self.full_battery_level

        # Charger disconnected
        if not is_charging and self.last_charging_state:
            if (
                is_full
                and notifications.get("full_battery")
                and not self.full_battery_notified
            ):
                if self._can_send_notifications():
                    send_notification(
                        title="Battery Full",
                        body=f"Battery charged to {percentage}%",
                        urgency="normal",
                        icon=icons["battery"].get("full", ""),
                        app_name="Battery",
                    )
                self.full_battery_notified = True
                self.charging_notified = False
                self.discharging_notified = False
            elif (
                not is_full
                and notifications.get("charging")
                and not self.discharging_notified
            ):
                if self._can_send_notifications():
                    send_notification(
                        title="Charger Disconnected",
                        body=f"Battery at {percentage}% - On battery power",
                        urgency="normal",
                        icon=icons["battery"].get("discharging", ""),
                        app_name="Battery",
                    )
                self.discharging_notified = True
                self.charging_notified = False

        # Charger connected
        elif (
            is_charging
            and not self.last_charging_state
            and notifications.get("charging")
            and not self.charging_notified
        ):
            if self._can_send_notifications():
                send_notification(
                    title="Charger Connected",
                    body=f"Battery at {percentage}% - Charging",
                    urgency="normal",
                    icon=icons["battery"].get("charging", ""),
                    app_name="Battery",
                )
            self.charging_notified = True
            self.discharging_notified = False

        if percentage < self.full_battery_level:
            self.full_battery_notified = False

        if notifications.get("low_battery"):
            threshold = notifications.get("low_threshold", 10)
            if (
                percentage <= threshold
                and not is_charging
                and not self.low_battery_notified
                and (self.last_percentage is None or self.last_percentage > threshold)
            ):
                if self._can_send_notifications():
                    send_notification(
                        title="Low Battery",
                        body=f"Battery at {percentage}%",
                        urgency="critical",
                        app_name="Battery",
                    )
                self.low_battery_notified = True
            elif percentage > threshold or is_charging:
                self.low_battery_notified = False
