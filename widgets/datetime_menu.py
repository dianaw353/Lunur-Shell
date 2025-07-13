from gi.repository import Gtk, GLib
from fabric.widgets.datetime import DateTime
from shared import ButtonWidget, Popover
from utils.functions import send_notification
from modules.launcher import Button
import time


class Timer(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # Timer title
        label = Gtk.Label(label="Timer:")
        label.set_halign(Gtk.Align.CENTER)
        label.set_name("timer-title")
        self.pack_start(label, False, False, 0)

        # Time entry fields
        inputs = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        inputs.set_halign(Gtk.Align.CENTER)

        self.minutes = Gtk.Entry()
        self.minutes.set_width_chars(2)
        self.minutes.set_max_length(2)
        self.minutes.set_alignment(0.5)
        inputs.pack_start(self.minutes, False, False, 0)

        colon = Gtk.Label(label=":")
        colon.set_halign(Gtk.Align.CENTER)
        inputs.pack_start(colon, False, False, 0)

        self.seconds = Gtk.Entry()
        self.seconds.set_width_chars(2)
        self.seconds.set_max_length(2)
        self.seconds.set_alignment(0.5)
        inputs.pack_start(self.seconds, False, False, 0)

        self.pack_start(inputs, False, False, 0)

        # Start button
        self.button = Button(label="Start")
        self.button.set_name("timer-start-button")
        self.button.set_halign(Gtk.Align.CENTER)
        self.button.connect("clicked", self.start)
        self.pack_start(self.button, False, False, 0)

        # Timer countdown label
        self.label = Gtk.Label(label="00:00")
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_name("timer-label")
        self.pack_start(self.label, False, False, 0)

        self.total = 0
        self._source = None

    def start(self, _):
        try:
            m = int(self.minutes.get_text() or "0")
            s = int(self.seconds.get_text() or "0")
            if m < 0 or s < 0 or s >= 60:
                raise ValueError
        except ValueError:
            self.label.set_text("Invalid input")
            return

        self.total = m * 60 + s
        if self.total == 0:
            self.label.set_text("Set time > 0")
            return

        self.minutes.set_sensitive(False)
        self.seconds.set_sensitive(False)
        self.button.set_sensitive(False)

        self.update_display()

        if self._source:
            GLib.source_remove(self._source)

        self._source = GLib.timeout_add_seconds(1, self._tick)

    def _tick(self):
        self.total -= 1
        self.update_display()

        if self.total <= 0:
            self.reset()
            send_notification(
                title="Timer Finished",
                body="Your countdown timer has ended.",
                urgency="normal",
                app_name="Timer",
            )
            return False

        return True

    def update_display(self):
        m = self.total // 60
        s = self.total % 60
        self.label.set_text(f"{m:02d}:{s:02d}")

    def reset(self):
        self.minutes.set_sensitive(True)
        self.seconds.set_sensitive(True)
        self.button.set_sensitive(True)
        self.minutes.set_text("")
        self.seconds.set_text("")
        self.label.set_text("00:00")
        self._source = None


class DateTimeWidget(ButtonWidget):
    def __init__(self, config):
        self.dt_config = config["date_time"]
        date_fmt = self.dt_config.get("format", "%b %d")
        clock_fmt = self.dt_config.get("clock_format", "24h")
        time_fmt = "%I:%M %p" if clock_fmt == "12h" else "%H:%M"
        full_fmt = f"{date_fmt} {time_fmt}"

        super().__init__(self.dt_config, name="date-time")

        self.datetime = DateTime(
            name="inner-date-time",
            formatters=[full_fmt],
        )
        self.box.children = (self.datetime,)
        self.datetime.show_all()

        self.timer = Timer()
        self.popup = None

        self.connect("clicked", self.toggle_popover)

    def do_format(self):
        fmt = self.datetime._formatters[self.datetime._current_index]
        return time.strftime(fmt, time.localtime())

    def toggle_popover(self, *_):
        if self.popup:
            if self.popup.get_visible():
                self.popup.hide()
            else:
                self.popup.open()
            return

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_name("date-menu")

        clock_fmt = self.dt_config.get("clock_format", "24h")
        time_fmt = "%I:%M %p" if clock_fmt == "12h" else "%H:%M"

        time_widget = DateTime(
            formatters=[time_fmt],
            name="popover-time"
        )

        calendar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        calendar_box.set_name("popover-calendar")

        calendar = Gtk.Calendar()
        calendar.set_name("calendar-widget")
        calendar_box.pack_start(calendar, True, True, 0)

        box.pack_start(time_widget, False, False, 0)
        box.pack_start(calendar_box, True, True, 0)
        box.pack_start(self.timer, False, False, 0)
        box.show_all()

        self.popup = Popover(
            content=box,
            point_to=self,
        )
        self.popup.open()
