from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.system_tray import SystemTray, SystemTrayItem
from shared.widget_container import HoverButton
from shared.reveal import HoverRevealer
from utils.widget_settings import BarConfig
from utils.icons import icons
from widgets.common.resolver import resolve_icon


class SystemTrayWidget(HoverRevealer):
    """System tray widget with configurable direction, transition, and tooltip."""

    def __init__(self, widget_config: BarConfig, **kwargs):
        self.config = widget_config.get("system_tray", {})
        self.tray_items = {}

        # Config options
        self.icon_size = self.config.get("icon_size", 16)
        slide_direction = self.config.get("slide_direction", "left")
        transition_duration = self.config.get("transition_duration", 250)
        self.tooltip_enabled = self.config.get("tooltip", True)

        # 1. Create Visible Child (Arrow Icon)
        arrow_icon_name = "right" if slide_direction == "left" else "left"
        self.toggle_icon = Image(
            icon_name=icons["ui"]["arrow"][arrow_icon_name],
            icon_size=self.icon_size,
            style_classes=["panel-icon", "toggle-icon"],
        )

        # 2. Create Hidden Child (Tray Box)
        self.tray_box = Box(spacing=4, orientation="horizontal")

        # 3. Initialize HoverRevealer
        super().__init__(
            visible_child=self.toggle_icon,
            hidden_child=self.tray_box,
            slide_direction=slide_direction,
            transition_duration=transition_duration,
            expanded_margin=self.icon_size,  # Spacing when opened
            **kwargs,
        )

        # System tray setup
        self.tray = SystemTray()
        self.tray.connect("item_added", self.on_item_added)
        self.tray.connect("item_removed", self.on_item_removed)

        # Populate existing
        for identifier, item in self.tray.items.items():
            self.on_item_added(self.tray, identifier)

    def on_item_added(self, _, identifier: str):
        item = self.tray.items.get(identifier)
        if not item:
            return

        button = HoverButton(
            tooltip_text=item.title if self.tooltip_enabled else "",
            style_classes="flat",
            margin_start=2,
            margin_end=2,
        )

        # Initial icon
        self._update_item_icon(item, button)

        # Connect click handler
        button.connect(
            "button-press-event", lambda btn, ev: self._on_item_click(btn, item, ev)
        )

        # Connect signals for reactive updates
        signals = ["icon_changed", "updated", "changed"]
        for sig in signals:
            try:
                if hasattr(item, "connect"):
                    item.connect(
                        sig, lambda *a, i=item, b=button: self._update_item_icon(i, b)
                    )
            except Exception:
                pass

        if hasattr(item, "dbus_iface"):
            for sig in ["NewIcon", "AttentionIconChanged"]:
                try:
                    item.dbus_iface.connect_to_signal(
                        sig, lambda *a, i=item, b=button: self._update_item_icon(i, b)
                    )
                except Exception:
                    pass

        self.tray_items[identifier] = (item, button)
        self.tray_box.add(button)
        button.show()

    def _update_item_icon(self, item: SystemTrayItem, button: HoverButton):
        """Update tray icon image for a given item."""
        try:
            pixbuf = resolve_icon(item, self.icon_size)
            if pixbuf:
                image = Image(pixbuf=pixbuf, pixel_size=self.icon_size)
                button.set_image(image)
        except Exception as e:
            print(f"Failed to update icon for {getattr(item, 'title', 'unknown')}: {e}")

    def _on_item_click(self, button, item: SystemTrayItem, event):
        if event.button in (1, 3):
            try:
                if getattr(item, "invoke_menu_for_event", None):
                    item.invoke_menu_for_event(event)
                else:
                    print(
                        f"No menu available for tray item {getattr(item, 'title', '')}"
                    )
            except Exception as e:
                print(f"Error handling tray item click: {e}")
            return True
        return False

    def on_item_removed(self, _, identifier: str):
        entry = self.tray_items.pop(identifier, None)
        if not entry:
            return

        _, button = entry
        self.tray_box.remove(button)
        button.destroy()

        # If no items left, close the reveal
        if not self.tray_items:
            self.set_expanded(False)
