from shared.widget_container import ButtonWidget
from utils.icons import icons
from utils.widget_utils import get_icon
from utils.widget_settings import BarConfig
from fabric.utils import exec_shell_command_async
from functools import lru_cache
import getpass


# Cache icon resolution to avoid repeated lookups
@lru_cache(maxsize=16)
def _get_powermenu_icon(icon_key, size):
    """Cached icon getter for power menu icons."""
    icon_name = icons["powermenu"][icon_key]
    return get_icon(icon_name, size=size)


class PowerWidget(ButtonWidget):
    """Base class for power menu widgets with optional label and tooltip."""

    def __init__(self, name, icon_key, config, command=None, **kwargs):
        """
        Args:
            name: Widget name for config lookup
            icon_key: Key in icons["powermenu"] dict
            config: Pre-resolved config dict for this widget
            command: Shell command to execute on click
        """
        super().__init__(config=config, name=name, **kwargs)

        # Get cached icon
        icon_size = config.get("icon_size", 16)
        self.icon_widget = _get_powermenu_icon(icon_key, icon_size)
        self.box.add(self.icon_widget)

        # Optional label
        label_text = config.get("label")
        if label_text and isinstance(label_text, str):
            self.set_label(label_text)

        # Optional tooltip
        tooltip_text = config.get("tooltip")
        if tooltip_text and isinstance(tooltip_text, str):
            self.set_tooltip_text(tooltip_text)

        # Connect command handler
        self.command = command
        if command:
            self.connect("button-press-event", self._on_click)

    def _on_click(self, *_):
        """Execute command on click."""
        exec_shell_command_async(self.command)
        return True


class SleepWidget(PowerWidget):
    def __init__(self, widget_config=None, **kwargs):
        if widget_config is None:
            widget_config = BarConfig()
        config = widget_config.get("sleep", widget_config)
        super().__init__(
            name="sleep",
            icon_key="sleep",
            config=config,
            command="systemctl suspend",
            **kwargs,
        )


class RebootWidget(PowerWidget):
    def __init__(self, widget_config=None, **kwargs):
        if widget_config is None:
            widget_config = BarConfig()
        config = widget_config.get("reboot", widget_config)
        super().__init__(
            name="reboot",
            icon_key="reboot",
            config=config,
            command="systemctl reboot",
            **kwargs,
        )


class LogoutWidget(PowerWidget):
    def __init__(self, widget_config=None, **kwargs):
        if widget_config is None:
            widget_config = BarConfig()
        config = widget_config.get("logout", widget_config)
        user = getpass.getuser()
        super().__init__(
            name="logout",
            icon_key="logout",
            config=config,
            command=f"loginctl terminate-user {user}",
            **kwargs,
        )


class ShutdownWidget(PowerWidget):
    def __init__(self, widget_config=None, **kwargs):
        if widget_config is None:
            widget_config = BarConfig()
        config = widget_config.get("shutdown", widget_config)
        super().__init__(
            name="shutdown",
            icon_key="shutdown",
            config=config,
            command="systemctl poweroff",
            **kwargs,
        )
