import re
from gi.repository import GObject, GLib, Playerctl, Gtk
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from shared.widget_container import EventBoxWidget
from shared import Popover
from utils.icons import icons
from utils import BarConfig, run_in_thread
from widgets.common.resolver import create_slide_revealer, set_expanded, on_leave


class PlayerctlMenu(Popover):
    def __init__(self, point_to_widget, player, config=None):
        self.player = player
        self.config = config or {}
        self.icon_size = self.config.get("icon_size", 16)
        self.poll_interval = self.config.get("menu_poll_interval", 1000)

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

        self._update_track_info_async()
        GLib.timeout_add(self.poll_interval, self._poll_tick)
        self._update_play_pause_icon()

    def _on_play_pause_clicked(self, *args):
        if not self.player:
            return
        try:
            status = getattr(self, "_last_playback_status", None)
            if status == Playerctl.PlaybackStatus.PLAYING:
                try:
                    self.player.pause()
                except Exception:
                    pass
            else:
                try:
                    self.player.play()
                except Exception:
                    pass
        except Exception as e:
            print(f"Error toggling play/pause: {e}")

    def _on_skip_back_clicked(self, *args):
        if not self.player:
            return
        try:
            self.player.previous()
        except Exception as e:
            print(f"Error skipping back: {e}")

    def _on_skip_forward_clicked(self, *args):
        if not self.player:
            return
        try:
            self.player.next()
        except Exception as e:
            print(f"Error skipping forward: {e}")

    def _update_play_pause_icon(self):
        # Use cached playback status to update icon; avoid accessing player.props
        try:
            status = getattr(self, "_last_playback_status", None)
            icon_name = (
                icons["playerctl"]["playing"]
                if status == Playerctl.PlaybackStatus.PLAYING
                else icons["playerctl"]["paused"]
            )
            GLib.idle_add(self._set_play_pause_icon, icon_name)
        except Exception as e:
            print(f"Error updating play/pause icon: {e}")

    def _set_play_pause_icon(self, icon_name):
        try:
            self.play_pause_icon.set_from_icon_name(icon_name)
        except Exception as e:
            print(f"Error setting play/pause icon: {e}")

    @run_in_thread
    def _update_track_info_async(self):
        # Use cached metadata to update menu; avoid reading player.props or get_position
        try:
            md = getattr(self, "_last_metadata", {}) or {}
            if not md:
                GLib.idle_add(self._reset_display)
                return
            title = md.get("xesam:title", "")
            artist = (md.get("xesam:artist") or [""])[0]
            time_text = "0:00 / 0:00"

            GLib.idle_add(
                self._update_labels_and_slider,
                title,
                artist,
                time_text,
                0,
                1,
            )
            self._update_play_pause_icon()
        except Exception as e:
            print(f"Error in track info update: {e}")
            GLib.idle_add(self._reset_display)

    def _update_labels_and_slider(self, title, artist, time_text, cur_sec, total_sec):
        self.title_label.set_text(re.sub(r"\r?\n", " ", title))
        self.artist_label.set_text(re.sub(r"\r?\n", " ", artist))
        self.time_label.set_text(time_text)

        adj = self.slider.get_adjustment()
        if adj:
            adj.set_upper(max(total_sec, 1))
            adj.set_value(cur_sec)

    def _poll_tick(self):
        if self.player:
            self._update_track_info_async()
        return True

    def _on_slider_click(self, widget, event):
        if not self.player:
            return False
        alloc = widget.get_allocation()
        if alloc.width <= 0:
            return False

        fraction = max(0, min(event.x / alloc.width, 1))
        total_sec = widget.get_adjustment().get_upper()
        seek_sec = int(total_sec * fraction)

        try:
            if hasattr(self.player, "set_position"):
                try:
                    self.player.set_position(seek_sec * 1_000_000)
                except Exception:
                    pass
            if hasattr(self.player, "play"):
                try:
                    self.player.play()
                except Exception:
                    pass
        except Exception as e:
            print(f"Error seeking in track: {e}")
        return False

    def _reset_display(self):
        self.title_label.set_text("")
        self.artist_label.set_text("")
        self.time_label.set_text("0:00 / 0:00")
        adj = self.slider.get_adjustment()
        if adj:
            adj.set_value(0)
            adj.set_upper(1)
        GLib.idle_add(self._set_play_pause_icon, icons["playerctl"]["paused"])


class PlayerctlWidget(EventBoxWidget):
    def __init__(self, widget_config=None, **kwargs):
        widget_config = widget_config or BarConfig()
        config = widget_config.get("playerctl", widget_config)
        super().__init__(**kwargs)

        self.config = config
        self.icon_size = config.get("icon_size", 16)
        self.slide_direction = config.get("slide_direction", "left")
        self.transition_duration = config.get("transition_duration", 250)
        self.tooltip_enabled = config.get("tooltip", True)
        self.poll_interval = config.get("poll_interval", 2000)
        self.player = None
        self.popup = None
        self._last_metadata = {}
        self._last_playback_status = None
        self._metadata_handler_id = None
        self._playback_handler_id = None
        self.player_name = None

        self.player_manager = Playerctl.PlayerManager.new()

        self.icon_widget = Image(
            icon_name=icons["playerctl"]["music"],
            icon_size=self.icon_size,
            style_classes=["panel-icon"],
        )
        self.label = Label(label="", style_classes="panel-text")
        label_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        label_container.pack_start(self.label, True, True, 4)
        label_container.set_hexpand(True)

        self.revealer = create_slide_revealer(
            child=label_container,
            slide_direction=self.slide_direction,
            transition_duration=self.transition_duration,
            initially_revealed=False,
        )
        self.revealer.set_hexpand(True)
        self.revealer.set_halign(Gtk.Align.FILL)

        self.icon_container = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.icon_container.set_hexpand(False)
        if self.slide_direction == "right":
            self.icon_container.pack_start(self.icon_widget, False, False, 0)
            self.icon_container.pack_start(self.revealer, True, True, 0)
        else:
            self.icon_container.pack_start(self.revealer, True, True, 0)
            self.icon_container.pack_start(self.icon_widget, False, False, 0)

        self.box.add(self.icon_container)
        self.box.show_all()

        self.player_manager.connect("player-vanished", self._on_player_vanished)
        self.player_manager.connect("name-appeared", self._on_player_appeared)
        self._setup_initial_player()
        GLib.timeout_add(self.poll_interval, self._poll_players)

        self.connect(
            "enter-notify-event",
            lambda *a: set_expanded(
                self.revealer, None, self.slide_direction, self.icon_size, expanded=True
            ),
        )
        self.connect(
            "leave-notify-event",
            lambda w, e: on_leave(
                widget=w,
                event=e,
                revealer=self.revealer,
                slide_direction=self.slide_direction,
                toggle_icon=None,
                icon_size=self.icon_size,
            ),
        )

        self.connect("button-press-event", self.on_click)

    def on_click(self, *_):
        if self.popup:
            self.popup.destroy()
            self.popup = None
        if not self.player:
            return
        self.popup = PlayerctlMenu(self, self.player, config=self.config)
        self.popup.open()

    @run_in_thread
    def _on_metadata_changed(self, player, metadata=None):
        # Use the metadata argument passed by the signal when possible to avoid
        # accessing `player.props` which can invoke g_object_get_property and
        # crash if the player has vanished.
        try:
            md = {}
            if metadata:
                try:
                    md = dict(metadata.unpack())
                except Exception:
                    md = {}
            # cache metadata for menu/other UI use
            self._last_metadata = md
            title = md.get("xesam:title", "")
            artist = (md.get("xesam:artist") or [""])[0]
            display_text = f"{title} – {artist}" if artist else title
            GLib.idle_add(self._update_label_text, display_text)
        except Exception as e:
            print(f"Error in metadata handler: {e}")

    def _on_playback_status_changed(self, player, status):
        """Cache playback status from signal to avoid reading player.props."""
        try:
            self._last_playback_status = status
            GLib.idle_add(self._update_play_pause_icon_from_status, status)
        except Exception as e:
            print(f"Error in playback status handler: {e}")

    def _update_play_pause_icon_from_status(self, status):
        """Update play/pause icon based on playback status (called from main thread)."""
        try:
            icon_name = (
                icons["playerctl"]["playing"]
                if status == Playerctl.PlaybackStatus.PLAYING
                else icons["playerctl"]["paused"]
            )
            if self.popup and hasattr(self.popup, "_set_play_pause_icon"):
                self.popup._set_play_pause_icon(icon_name)
        except Exception as e:
            print(f"Error updating play/pause from status: {e}")

    def _fetch_initial_metadata(self):
        """Request initial metadata from player by checking playback status.
        
        This indirectly triggers metadata signal to fire without directly reading props.
        """
        if not self.player:
            return False
        try:
            # Call playback_status() to trigger any pending signals
            # Don't read the return value, just call the method to nudge the player
            try:
                _ = self.player.call_playback_status_sync()
            except Exception:
                pass
            # Also try calling get_metadata() if available
            try:
                _ = self.player.call_metadata_sync()
            except Exception:
                pass
        except Exception:
            pass
        return False  # Don't reschedule

    def _update_label_text(self, text):
        self.label.set_text(text)
        if self.tooltip_enabled:
            self.set_tooltip_text(text)
        if self.popup:
            self.popup._update_track_info_async()

    def _setup_initial_player(self):
        try:
            player_names = self.player_manager.props.player_names
        except Exception:
            player_names = []

        if player_names and isinstance(player_names[0], Playerctl.PlayerName):
            try:
                player = Playerctl.Player.new_from_name(player_names[0])
                self._set_player(player)
            except Exception:
                pass

    def _poll_players(self):
        try:
            player_names = self.player_manager.props.player_names
        except Exception:
            player_names = []

        if not player_names and self.player:
            self._clear_player()
        elif player_names:
            current = None
            try:
                current = self.player_name if self.player else None
            except Exception:
                current = None
            available = [p for p in player_names]
            if current not in available:
                try:
                    player = Playerctl.Player.new_from_name(available[0])
                    self._set_player(player)
                except Exception:
                    pass
        return True

    def _on_player_vanished(self, _, player):
        try:
            # Clear references immediately if the vanished player matches
            # the current player name. Avoid accessing player.props on the
            # vanished object where possible.
            try:
                vanished_name = None
                try:
                    vanished_name = player.props.player_name
                except Exception:
                    vanished_name = None
                if vanished_name and self.player_name and vanished_name == self.player_name:
                    self._clear_player()
            except Exception:
                # Fallback: if we have a player object but can't read names,
                # just clear to be safe.
                if self.player:
                    self._clear_player()
        except Exception as e:
            print(f"Error in player vanished handler: {e}")

    def _on_player_appeared(self, _, player_name_obj):
        if not self.player and isinstance(player_name_obj, Playerctl.PlayerName):
            try:
                player = Playerctl.Player.new_from_name(player_name_obj)
                self._set_player(player)
            except Exception:
                pass

    def _set_player(self, player):
        # Disconnect old handlers safely
        if self.player:
            try:
                if getattr(self, "_metadata_handler_id", None) is not None:
                    try:
                        self.player.disconnect(self._metadata_handler_id)
                    except Exception:
                        try:
                            self.player.disconnect_by_func(self._on_metadata_changed)
                        except Exception:
                            pass
            except Exception:
                pass

        self.player = player
        # Reset caches
        self._last_metadata = {}
        self._last_playback_status = None
        self.player_name = None
        self._metadata_handler_id = None
        self._playback_handler_id = None

        if player:
            try:
                # Connect metadata signal and store handler id
                try:
                    self._metadata_handler_id = player.connect("metadata", self._on_metadata_changed)
                except Exception:
                    self._metadata_handler_id = None
                # Connect playback status changes if available
                try:
                    self._playback_handler_id = player.connect("playback-status", self._on_playback_status_changed)
                except Exception:
                    self._playback_handler_id = None
                
                # Schedule a deferred initial metadata fetch on the main thread
                # This avoids race conditions and lets signals settle first
                GLib.idle_add(self._fetch_initial_metadata)
            except Exception as e:
                print(f"Error setting up player: {e}")

    def _clear_player(self):
        # Disconnect any stored handlers from the current player before clearing
        try:
            if self.player:
                if getattr(self, "_metadata_handler_id", None) is not None:
                    try:
                        self.player.disconnect(self._metadata_handler_id)
                    except Exception:
                        try:
                            self.player.disconnect_by_func(self._on_metadata_changed)
                        except Exception:
                            pass
                if getattr(self, "_playback_handler_id", None) is not None:
                    try:
                        self.player.disconnect(self._playback_handler_id)
                    except Exception:
                        try:
                            self.player.disconnect_by_func(self._on_playback_status_changed)
                        except Exception:
                            pass
        except Exception:
            pass
        self.player = None
        self.label.set_text("")
        if self.tooltip_enabled:
            self.set_tooltip_text("")
        if self.popup:
            self.popup.destroy()
            self.popup = None
