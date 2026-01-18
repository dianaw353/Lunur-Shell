from fabric.hyprland.widgets import get_hyprland_connection
from fabric.utils import cooldown, exec_shell_command_async, invoke_repeater
from fabric.widgets.scale import Scale
from fabric.widgets.box import Box

from gi.repository import Gtk

from shared.buttons import QSChevronButton
from shared.submenu import QuickSubMenu
from utils.functions import is_app_running, toggle_command
from utils.icons import text_icons


class HyprSunsetSubMenu(QuickSubMenu):
    """A submenu to display application-specific audio controls."""

    def __init__(self, **kwargs):
        self.scan_button = None

        self._hyprland_connection = get_hyprland_connection()

        self.scale = Scale(
            name="hyprsunset-scale",
            draw_value=True,
            digits=0,
            increments=(100, 100),
            max_value=10000,
            min_value=1000,
            value=2600,
            style_classes=["qs-slider"],
            h_expand=True,
        )

        # Wrap the scale in a box with proper sizing
        scale_container = Box(
            children=[self.scale],
            h_expand=True,
            v_expand=False,
        )

        super().__init__(
            title="HyprSunset",
            title_icon=text_icons["nightlight"]["enabled"],
            name="hyprsunset-sub-menu",
            scan_button=self.scan_button,
            child=scale_container,
            **kwargs,
        )

        # Connect the slider immediately
        self.scale.connect("value-changed", self.on_scale_move)
        invoke_repeater(1000, self.update_scale)

    @cooldown(0.1)
    def on_scale_move(self, scale: Scale):
        temperature = int(scale.get_value())
        exec_shell_command_async(
            f"hyprctl hyprsunset temperature {temperature}",
            lambda *_: self._update_ui(temperature),
        )
        return True

    def update_scale(self, *_):
        if is_app_running("hyprsunset"):
            self.scale.set_sensitive(True)
            exec_shell_command_async(
                "hyprctl hyprsunset temperature",
                self._update_ui,
            )
        else:
            self.scale.set_sensitive(False)

    def _update_ui(self, moved_pos: str | int):
        # Update the scale value based on the current temperature
        try:
            sanitized_value = int(
                moved_pos.strip("\n").strip("") if isinstance(moved_pos, str) else moved_pos
            )
        except ValueError:
            # If the output is not a valid integer (e.g., error message), skip updating
            return

        # Avoid unnecessary updates if the value hasn't changed
        if sanitized_value == round(self.scale.get_value()):
            return

        self.scale.set_value(sanitized_value)
        self.scale.set_tooltip_text(f"{sanitized_value}K")


class HyprSunsetToggle(QSChevronButton):
    """A widget to display a toggle button for Wifi."""

    def __init__(self, submenu: QuickSubMenu, popup, **kwargs):
        super().__init__(
            style_classes=["quicksettings-toggler"],
            action_icon=text_icons["nightlight"]["disabled"],
            pixel_size=20,
            action_label="Disabled",
            submenu=submenu,
            **kwargs,
        )

        self.popup = popup
        self.action_button.set_sensitive(True)

        self.connect("action-clicked", self.on_action)

        invoke_repeater(1000, self.update_action_button)

    def on_action(self, *_):
        """Handle the action button click event."""
        # Get current slider value for dynamic command
        current_temp = int(self.submenu.scale.get_value())
        is_now_running = toggle_command("hyprsunset", f"hyprsunset -t {current_temp}")
        
        # Update UI immediately
        if is_now_running:
            self.action_icon.set_label(text_icons["nightlight"]["enabled"])
            self.action_label.set_label("Enabled")
            self.add_style_class("active")
            self.submenu.scale.set_sensitive(True)
        else:
            self.action_icon.set_label(text_icons["nightlight"]["disabled"])
            self.action_label.set_label("Disabled")
            self.remove_style_class("active")
            self.submenu.scale.set_sensitive(False)
        
        return True

    def update_action_button(self, *_):
        self.is_running = is_app_running("hyprsunset")

        if self.is_running:
            self.action_icon.set_label(text_icons["nightlight"]["enabled"])
            self.action_label.set_label("Enabled")
            self.add_style_class("active")
        else:
            self.action_icon.set_label(text_icons["nightlight"]["disabled"])
            self.action_label.set_label("Disabled")
            self.remove_style_class("active")
