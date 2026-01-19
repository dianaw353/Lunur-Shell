# widgets/quick_settings/quick_settings_menu.py

from gi.repository import Gtk
from fabric.widgets.box import Box
from fabric.widgets.grid import Grid
from .sliders.brightness import BrightnessSlider
from .sliders.volume import VolumeSlider
from .sliders.microphone import MicrophoneSlider
from .togglers import NotificationQuickSetting
from .submenu.wifi import WifiQuickSetting
from .submenu.bluetooth import BluetoothQuickSetting
from .submenu.hyprsunset import (
    HyprSunsetSubMenu,
    HyprSunsetToggle,
)

from shared.pop_over import Popover


class SlidersContainer(Box):
    """Container for brightness, volume, and microphone sliders."""

    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            style_classes="sliders-container",
        )
        self.brightness_slider = BrightnessSlider()
        self.pack_start(self.brightness_slider, False, False, 0)
        self.volume_slider = VolumeSlider()
        self.pack_start(self.volume_slider, False, False, 0)
        self.mic_slider = MicrophoneSlider()
        self.pack_start(self.mic_slider, False, False, 0)


class QuickSettingsMenu(Popover):
    def __init__(self, point_to_widget, config):
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content_box.set_name("quick-settings-menu")

        self.sliders = SlidersContainer()
        content_box.pack_start(self.sliders, False, False, 0)

        self.grid = Grid(
            row_spacing=10,
            column_spacing=10,
            column_homogeneous=True,
            row_homogeneous=True,
        )
        self.wifi_btn = WifiQuickSetting()
        self.bt_btn = BluetoothQuickSetting()
        self.notification_btn = NotificationQuickSetting()
        self.hyprsunset = HyprSunsetToggle(submenu=HyprSunsetSubMenu(), popup=self)

        self.grid.attach(self.wifi_btn, 0, 0, 1, 1)
        self.grid.attach(self.bt_btn, 1, 0, 1, 1)
        self.grid.attach(self.notification_btn, 0, 1, 1, 1)
        self.grid.attach(self.hyprsunset, 1, 1, 1, 1)

        content_box.pack_start(self.grid, True, True, 0)

        # Add the hyprsunset submenu to the content box
        content_box.pack_start(self.hyprsunset.submenu, False, False, 0)

        # Connect the chevron click to toggle the submenu
        self.hyprsunset.connect("reveal-clicked", self._toggle_hyprsunset_submenu)

        content_box.show_all()
        super().__init__(content=content_box, point_to=point_to_widget)

    def _toggle_hyprsunset_submenu(self, *_):
        """Toggle the HyprSunset submenu visibility."""
        self.hyprsunset.submenu.toggle_reveal()
