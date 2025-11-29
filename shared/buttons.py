from functools import partial

from fabric.core.service import Signal
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.label import Label

from utils.bezier import cubic_bezier
from utils.constants import ASSETS_DIR
from utils.icons import icons, text_icons
from utils.widget_utils import nerd_font_icon, setup_cursor_hover

from .widget_container import BaseWidget


class HoverButton(Button, BaseWidget):
    """A container for button with hover effects."""

    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
        )

        setup_cursor_hover(self)


class QSToggleButton(Box, BaseWidget):
    """A widget to display a toggle button for quick settings."""

    @Signal
    def action_clicked(self) -> None: ...

    def __init__(
        self,
        action_label: str = "My Label",
        action_icon: str = icons["fallback"]["package"],
        pixel_size: int = 18,
        **kwargs,
    ):
        self.pixel_size = pixel_size

        # required for chevron button
        self.box = Box()

        # Action button can hold an icon and a label NOTHING MORE
        self.action_icon = nerd_font_icon(
            icon=action_icon,
            props={
                "style_classes": ["panel-font-icon"],
                "style": f"font-size: {self.pixel_size}px;",
            },
        )

        self.action_label = Label(
            style_classes=["panel-text"],
            label=action_label,
            ellipsization="end",
            h_align="start",
            h_expand=True,
        )

        self.action_button = HoverButton(
            style_classes=["quicksettings-toggle-action"],
            on_clicked=self._action,
        )

        self.action_button.set_size_request(170, 20)

        self.action_button.add(
            Box(
                h_align="start",
                v_align="center",
                style_classes=["quicksettings-toggle-action-box"],
                children=[self.action_icon, self.action_label],
            ),
        )

        self.box.add(self.action_button)

        super().__init__(
            name="quicksettings-togglebutton",
            h_align="start",
            v_align="start",
            children=[self.box],
            **kwargs,
        )

    def _action(self, *_):
        self.emit("action-clicked")

    def set_active_style(self, action: bool, *_) -> None:
        self.set_style_classes("") if not action else self.set_style_classes("active")

    def set_action_label(self, label: str):
        self.action_label.set_label(label.strip())

    def set_action_icon(self, icon: str):
        self.action_icon.set_label(icon)

