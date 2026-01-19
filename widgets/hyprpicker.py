from gi.repository import Gtk, Gdk
from fabric.widgets.label import Label
from fabric.utils import exec_shell_command_async, get_relative_path
from utils.config import widget_config
from utils.widget_settings import BarConfig
from shared.widget_container import ButtonWidget
from utils.icons import text_icons
import os

hyprpicker = widget_config["hyprpicker"]


class HyprPickerButton(ButtonWidget):
    def __init__(self, widget_config: BarConfig, **kwargs):
        super().__init__(
            config=widget_config["hyprpicker"],
            name="hyprpicker-button",
            **kwargs,
        )

        self.initialized = False
        self.script_file = None

        icon_char = text_icons["ui"]["hyprpicker"]
        font_size = self.config.get("icon_size", 14)

        self.icon_label = Label(
            label=icon_char,
            style_classes="panel-icon",
        )
        self.icon_label.set_size_request(font_size, font_size)
        self.icon_label.set_halign(Gtk.Align.CENTER)
        self.icon_label.set_valign(Gtk.Align.CENTER)

        self.box.children = (self.icon_label,)

        if self.config.get("tooltip"):
            self.set_tooltip_text("Pick a color")

        self.connect("button-press-event", self.on_button_press)

    def lazy_init(self):
        if not self.initialized:
            self.script_file = get_relative_path("../assets/scripts/hyprpicker.sh")
            if not os.path.isfile(self.script_file):
                self.set_sensitive(False)
                self.set_tooltip_text("Script not found")
                return
            self.initialized = True

    def on_button_press(self, widget, event):
        self.lazy_init()
        if not self.initialized:
            return

        command = self.script_file
        if self.config.get("quiet", False):
            command += " --no-notify"

        if event.type == Gdk.EventType.BUTTON_PRESS:
            if event.button == 1:
                exec_shell_command_async(f"{command} -hex", lambda *_: None)
            elif event.button == 2:
                exec_shell_command_async(f"{command} -hsv", lambda *_: None)
            elif event.button == 3:
                exec_shell_command_async(f"{command} -rgb", lambda *_: None)
