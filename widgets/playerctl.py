# widgets/playerctl.py

import re
import utils.functions as helpers
from gi.repository import GLib, Playerctl, Gtk
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from shared.pop_over import Popover
from shared.reveal import HoverRevealer
from utils.icons import icons
from utils.widget_settings import BarConfig
from utils.exceptions import PlayerctlImportError

try:
    from services.playerctl import PlayerctlService
except ImportError:
    raise PlayerctlImportError()


class PlayerctlMenu(Popover):
    """
    The popup menu containing playback controls, seek bar, and track info.
    (Unchanged from original)
    """

    def __init__(self, point_to_widget, service, config=None):
        self.service = service
        self.config = config or {}
        self.icon_size = self.config.get("icon_size", 16)
        self.poll_interval = self.config.get("menu_poll_interval", 1000)
        self._poll_source_id = None
        self._destroyed = False

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content_box.set_name("playerctl-menu")
        content_box.set_halign(Gtk.Align.FILL)
        content_box.set_hexpand(True)

        self.track_frame = Gtk.Frame()
        self.track_frame.set_shadow_type(Gtk.ShadowType.IN)
        self.track_frame.set_name("playerctl-track-frame")
        for side in ("top", "bottom", "start", "end"):
            getattr(self.track_frame, f"set_margin_{side}")(2)

        self.title_label = Label(label="", style_classes="panel-text-title")
        self.artist_label = Label(label="", style_classes="panel-text-artist")
        self.time_label = Label(label="0:00 / 0:00", style_classes="panel-text-time")
        self.title_label.set_halign(Gtk.Align.FILL)
        self.artist_label.set_halign(Gtk.Align.FILL)
        self.time_label.set_halign(Gtk.Align.END)

        adj = Gtk.Adjustment(
            value=0, lower=0, upper=1, step_increment=1, page_increment=5
        )
        self.slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        self.slider.set_draw_value(False)
        self.slider.set_hexpand(True)
        self.slider.set_halign(Gtk.Align.FILL)
        self.slider.connect("button-press-event", self._on_slider_click)

        self.skip_back_button = Gtk.Button()
        self.skip_back_button.connect("clicked", self._on_skip_back_clicked)
        self.skip_back_icon = Image(
            icon_name=icons["playerctl"]["prev"],
            icon_size=self.icon_size,
            style_classes=["panel-icon"],
        )
        self.skip_back_button.add(self.skip_back_icon)

        self.play_pause_button = Gtk.Button()
        self.play_pause_button.connect("clicked", self._on_play_pause_clicked)
        self.play_pause_icon = Image(
            icon_name=icons["playerctl"]["paused"],
            icon_size=self.icon_size,
            style_classes=["panel-icon"],
        )
        self.play_pause_button.add(self.play_pause_icon)

        self.skip_forward_button = Gtk.Button()
        self.skip_forward_button.connect("clicked", self._on_skip_forward_clicked)
        self.skip_forward_icon = Image(
            icon_name=icons["playerctl"]["next"],
            icon_size=self.icon_size,
            style_classes=["panel-icon"],
        )
        self.skip_forward_button.add(self.skip_forward_icon)

        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.pack_start(self.skip_back_button, False, False, 0)
        controls_box.pack_start(self.play_pause_button, False, False, 0)
        controls_box.pack_start(self.skip_forward_button, False, False, 0)

        track_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        track_box.pack_start(self.title_label, False, False, 0)
        track_box.pack_start(self.artist_label, False, False, 0)

        time_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        time_box.pack_start(self.slider, True, True, 0)
        time_box.pack_end(self.time_label, False, False, 0)
        track_box.pack_start(time_box, False, False, 0)
        track_box.pack_start(controls_box, False, False, 2)

        self.track_frame.add(track_box)
        content_box.add(self.track_frame)
        content_box.show_all()
        super().__init__(content=content_box, point_to=point_to_widget)

        self.connect("destroy", self._on_destroy)

        self._update_track_info()
        self._poll_source_id = GLib.timeout_add(self.poll_interval, self._poll_tick)

    def _on_destroy(self, *args):
        self._destroyed = True
        if self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None

    def _on_play_pause_clicked(self, *args):
        if self._destroyed:
            return
        self.service.player_action("play_pause")

    def _on_skip_back_clicked(self, *args):
        if self._destroyed:
            return
        self.service.player_action("previous")

    def _on_skip_forward_clicked(self, *args):
        if self._destroyed:
            return
        self.service.player_action("next")

    def _update_play_pause_icon(self, status):
        if self._destroyed:
            return
        icon_name = (
            icons["playerctl"]["playing"]
            if status == Playerctl.PlaybackStatus.PLAYING
            else icons["playerctl"]["paused"]
        )
        try:
            self.play_pause_icon.set_from_icon_name(icon_name)
        except Exception:
            pass

    def _update_track_info(self):
        if self._destroyed:
            return

        metadata = self.service.get_cached_metadata()
        if not metadata:
            self._reset_display()
            return

        title = metadata.get("title", "")
        artist = metadata.get("artist", "")
        length_us = metadata.get("length", 0)
        status = metadata.get("status", Playerctl.PlaybackStatus.STOPPED)
        pos_us = metadata.get("position", 0)

        cur_sec, total_sec = int(pos_us / 1e6), int(length_us / 1e6)
        cur_min, cur_s = divmod(cur_sec, 60)
        tot_min, tot_s = divmod(total_sec, 60)
        time_text = f"{cur_min}:{cur_s:02} / {tot_min}:{tot_s:02}"

        try:
            self.title_label.set_text(
                helpers.truncate(re.sub(r"\r?\n", " ", title), 30)
            )
            self.artist_label.set_text(
                helpers.truncate(re.sub(r"\r?\n", " ", artist), 30)
            )
            self.time_label.set_text(time_text)

            adj = self.slider.get_adjustment()
            if adj:
                adj.set_upper(max(total_sec, 1))
                adj.set_value(cur_sec)

            self._update_play_pause_icon(status)
        except Exception as e:
            print(f"Error updating display: {e}")

    def _poll_tick(self):
        if self._destroyed:
            self._poll_source_id = None
            return False

        # Request service to update position
        self.service.update_position()
        self._update_track_info()
        return True

    def _on_slider_click(self, widget, event):
        if self._destroyed:
            return False

        alloc = widget.get_allocation()
        if alloc.width <= 0:
            return False

        fraction = max(0, min(event.x / alloc.width, 1))
        total_sec = widget.get_adjustment().get_upper()
        seek_sec = int(total_sec * fraction)

        self.service.player_action("seek", seek_sec * 1_000_000)
        return False

    def _reset_display(self):
        if self._destroyed:
            return
        try:
            self.title_label.set_text("")
            self.artist_label.set_text("")
            self.time_label.set_text("0:00 / 0:00")
            adj = self.slider.get_adjustment()
            if adj:
                adj.set_value(0)
                adj.set_upper(1)
            self.play_pause_icon.set_from_icon_name(icons["playerctl"]["paused"])
        except Exception:
            pass


class PlayerctlWidget(HoverRevealer):
    def __init__(self, widget_config=None, **kwargs):
        widget_config = widget_config or BarConfig()
        config = widget_config.get("playerctl", widget_config)

        self.config = config
        self.icon_size = config.get("icon_size", 16)
        slide_direction = config.get("slide_direction", "left")
        transition_duration = config.get("transition_duration", 250)

        self.tooltip_enabled = config.get("tooltip", True)
        self.poll_interval = config.get("poll_interval", 2000)

        self.popup = None
        self._poll_source_id = None
        self._destroyed = False

        # Create the service
        self.service = PlayerctlService()

        # 1. Create Visible Child (Icon)
        self.icon_widget = Image(
            icon_name=icons["playerctl"]["music"],
            icon_size=self.icon_size,
            style_classes=["panel-icon"],
        )

        # 2. Create Hidden Child (Label Container)
        self.label = Label(label="", style_classes="panel-text")
        label_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_container.pack_start(self.label, True, True, 4)
        # Ensure the container takes available space
        label_container.set_hexpand(True)

        # 3. Initialize the HoverRevealer
        super().__init__(
            visible_child=self.icon_widget,
            hidden_child=label_container,
            slide_direction=slide_direction,
            transition_duration=transition_duration,
            expanded_margin=self.icon_size,  # Use icon size for spacing logic similar to original
            **kwargs,
        )

        # Connect to service signals
        self.service.connect("metadata-changed", self._on_metadata_changed)
        self.service.connect("player-changed", self._on_player_changed)

        self._poll_source_id = GLib.timeout_add(self.poll_interval, self._poll_tick)

        self.connect("destroy", self._on_destroy)

    def _on_destroy(self, *args):
        self._destroyed = True
        if self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None
        self.service.destroy()
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def _on_metadata_changed(self, service):
        """Handle metadata changed signal from service."""
        if self._destroyed:
            return
        self._update_display()

    def _on_player_changed(self, service):
        """Handle player changed signal from service."""
        if self._destroyed:
            return
        if not self.service.is_valid:
            self._clear_display()

    def _update_display(self):
        """Update the label with cached metadata."""
        if self._destroyed:
            return

        metadata = self.service.get_cached_metadata()
        if not metadata:
            self._clear_display()
            return

        title = metadata.get("title", "")
        artist = metadata.get("artist", "")
        display_text = helpers.truncate(f"{title} – {artist}" if artist else title, 20)

        try:
            self.label.set_text(display_text)
            if self.tooltip_enabled:
                self.set_tooltip_text(display_text)
        except Exception:
            pass

    def _clear_display(self):
        """Clear the display."""
        if self._destroyed:
            return False

        try:
            self.label.set_text("")
            if self.tooltip_enabled:
                self.set_tooltip_text("")
        except Exception:
            pass

        if self.popup:
            self.popup.destroy()
            self.popup = None

        return False

    def on_click(self, widget, event):
        """
        Override HoverRevealer.on_click to open the popup
        instead of just toggling the animation.
        """
        if self.popup:
            self.popup.destroy()
            self.popup = None
            return

        if not self.service.is_valid:
            return

        self.popup = PlayerctlMenu(self, self.service, config=self.config)
        self.popup.open()

    def _poll_tick(self):
        """Periodic poll to check state."""
        if self._destroyed:
            return False

        self.service.check_players()
        return True
