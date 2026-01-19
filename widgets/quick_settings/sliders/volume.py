# widgets/quick_settings/sliders/volume.py

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.revealer import Revealer
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from fabric.widgets.scale import Scale
from fabric.utils import logger
from gi.repository import Gtk
from .slider_row import SliderRow
from services import audio_service
from utils.icons import icons
from utils.widget_utils import get_audio_icon_name
from shared.separator import Separator


class AppVolumeControl(Box):
    """Individual app volume control with icon."""

    def __init__(self, stream, on_close=None):
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            style_classes=["app-volume-slider-row"],
        )

        self.stream = stream
        self.on_close = on_close
        self._updating = False

        # App icon
        self.icon = Image(style_classes=["app-volume-icon"])
        self._set_app_icon()
        self.pack_start(self.icon, False, False, 0)

        # Volume slider
        self.scale = Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            min_value=0,
            max_value=100,
            value=round(stream.volume),
            draw_value=False,
            h_expand=True,
            style_classes=["qs-slider", "app-slider"],
        )
        self.scale.connect("value-changed", self._on_value_changed)
        self.pack_start(self.scale, True, True, 0)

        # Percentage label
        self.percentage_label = Label(
            label=f"{int(stream.volume)}%",
            style_classes=["slider-percentage"],
        )
        self.percentage_label.set_size_request(45, -1)
        self.pack_start(self.percentage_label, False, False, 0)

        # Connect to stream changes
        self.stream.connect("notify::volume", self._on_stream_volume_changed)
        self.stream.connect("notify::muted", self._on_stream_volume_changed)
        self.stream.connect("closed", self._on_stream_closed)

    def _set_app_icon(self):
        """Set the app icon from stream icon name or use fallback."""
        icon_size = 20

        # Try to get icon from stream
        if hasattr(self.stream, "icon_name") and self.stream.icon_name:
            try:
                # Try to load as icon name first
                self.icon.set_from_icon_name(self.stream.icon_name, icon_size)
                return
            except Exception:
                logger.error("[Quick settings] Loading volume icon failed: {e}")

        # Try to get icon from application_id
        if hasattr(self.stream, "application_id") and self.stream.application_id:
            try:
                # Try common icon name patterns
                app_id = self.stream.application_id.lower()
                possible_icons = [
                    app_id,
                    f"{app_id}-symbolic",
                    self.stream.application_id,
                ]

                for icon_name in possible_icons:
                    try:
                        self.icon.set_from_icon_name(icon_name, icon_size)
                        return
                    except Exception as e:
                        logger.error(
                            f"[Quick settings] Loading icon {icon_name} failed: {e}"
                        )
            except Exception as e:
                logger.error(f"[Quick settings] Failed to fetch app icon: {e}")

        # Fallback to audio icon
        self.icon.set_from_icon_name(icons["audio"]["volume"]["medium"], icon_size)

    def _on_value_changed(self, scale):
        if self._updating:
            return

        value = scale.get_value()
        self.percentage_label.set_label(f"{int(value)}%")

        if self.stream:
            self.stream.volume = value

    def _on_stream_volume_changed(self, *_):
        if self.stream:
            self._updating = True
            volume = round(self.stream.volume)
            self.scale.set_value(volume)
            self.percentage_label.set_label(f"{int(volume)}%")
            self._updating = False

    def _on_stream_closed(self, *_):
        """Stream closed, notify parent to remove this widget."""
        if self.on_close:
            self.on_close(self.stream.id)


class VolumeSlider(Box):
    """Volume slider with dropdown for individual app controls."""

    def __init__(self):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            style_classes=["volume-slider-container"],
        )

        self.audio = audio_service

        # Main row (slider + expand button)
        self.main_row = Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )

        # Get initial volume
        initial_volume = 50
        if self.audio.speaker:
            initial_volume = round(self.audio.speaker.volume)

        # Volume slider
        self.volume_slider = SliderRow(
            icon_name=icons["audio"]["volume"]["medium"],
            min_value=0,
            max_value=100,
            initial_value=initial_volume,
            on_change=self._set_volume,
            style_class="volume-slider-row",
        )
        self.main_row.pack_start(self.volume_slider, True, True, 0)

        # Expand/collapse button with icon
        self.expand_icon = Image(style_classes=["volume-expand-icon"])
        self.expand_icon.set_from_icon_name(icons["ui"]["arrow"]["down"], 16)

        self.expand_button = Button(
            child=self.expand_icon,
            style_classes=["volume-expand-button"],
        )
        self.expand_button.connect("clicked", self._toggle_apps)
        self.main_row.pack_start(self.expand_button, False, False, 0)

        self.pack_start(self.main_row, False, False, 0)

        # Separator
        self.separator = Separator(
            orientation="horizontal",
            style_classes=["app-volume-separator"],
        )

        # Apps container with separator
        self.apps_wrapper = Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )
        self.apps_wrapper.pack_start(self.separator, False, False, 0)

        self.apps_box = Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=5,
            style_classes=["app-volume-container"],
        )
        self.apps_wrapper.pack_start(self.apps_box, False, False, 0)

        # Revealer for smooth animation
        self.revealer = Revealer(
            child=self.apps_wrapper,
            reveal_child=False,
            transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
            transition_duration=200,
        )
        self.pack_start(self.revealer, False, False, 0)

        # Track app controls
        self.app_controls = {}

        # Connect to audio service
        self.audio.connect("notify::speaker", self._on_speaker_changed)
        self.audio.connect("stream-added", self._on_stream_added)
        self.audio.connect("stream-removed", self._on_stream_removed)

        if self.audio.speaker:
            self._connect_speaker_signals()

        self._update_icon(initial_volume)
        self._populate_apps()

    def _connect_speaker_signals(self):
        if self.audio.speaker:
            self.audio.speaker.connect("notify::volume", self._on_volume_changed)
            self.audio.speaker.connect("notify::muted", self._on_volume_changed)

    def _on_speaker_changed(self, *_):
        self._connect_speaker_signals()
        self._on_volume_changed()

    def _set_volume(self, value: float):
        if self.audio.speaker:
            self.audio.speaker.volume = value

    def _on_volume_changed(self, *_):
        if self.audio.speaker:
            volume = round(self.audio.speaker.volume)
            muted = self.audio.speaker.muted
            self.volume_slider.set_value(volume)
            self._update_icon(volume, muted)

    def _update_icon(self, volume: float, muted: bool = False):
        try:
            icon_info = get_audio_icon_name(volume, muted)
            icon_name = icon_info.get("icon", icons["audio"]["volume"]["medium"])
            self.volume_slider.set_icon(icon_name)
        except Exception:
            pass

    def _toggle_apps(self, *_):
        current_state = self.revealer.get_reveal_child()
        new_state = not current_state
        self.revealer.set_reveal_child(new_state)
        self._update_expand_icon(new_state)

    def _update_expand_icon(self, expanded: bool):
        """Update arrow icon based on expansion state."""
        icon_name = (
            icons["ui"]["arrow"]["up"] if expanded else icons["ui"]["arrow"]["down"]
        )
        self.expand_icon.set_from_icon_name(icon_name, 16)

    def _populate_apps(self):
        """Populate app volume controls."""
        # Clear existing
        for child in self.apps_box.get_children():
            self.apps_box.remove(child)
        self.app_controls.clear()

        # Add current application streams
        if self.audio.applications:
            for stream in self.audio.applications:
                self._add_app_control(stream)

    def _add_app_control(self, stream):
        """Add a single app volume control."""
        if stream and stream.id not in self.app_controls:
            control = AppVolumeControl(stream, on_close=self._remove_app_control)
            self.app_controls[stream.id] = control
            self.apps_box.pack_start(control, False, False, 0)
            control.show_all()

    def _remove_app_control(self, stream_id):
        """Remove an app volume control by stream ID."""
        if stream_id in self.app_controls:
            control = self.app_controls[stream_id]
            parent = control.get_parent()
            if parent:
                parent.remove(control)
            del self.app_controls[stream_id]

    def _on_stream_added(self, audio, stream):
        """Handle new application stream."""
        if stream and hasattr(stream, "type") and stream.type == "application":
            self._add_app_control(stream)

    def _on_stream_removed(self, audio, stream_id):
        """Handle removed application stream."""
        self._remove_app_control(stream_id)
