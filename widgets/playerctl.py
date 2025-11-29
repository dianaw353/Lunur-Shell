import re
from gi.repository import GObject, GLib, Playerctl, Gtk
from fabric.widgets.label import Label
from fabric.widgets.image import Image
from shared.widget_container import EventBoxWidget
from shared import Popover
from utils.icons import icons
from utils import BarConfig
from widgets.common.resolver import create_slide_revealer, set_expanded, on_leave


class PlayerctlMenu(Popover):
    def __init__(self, point_to_widget, parent_widget, config=None):
        self.parent_widget = parent_widget
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
        self.parent_widget.player_action("play_pause")

    def _on_skip_back_clicked(self, *args):
        if self._destroyed:
            return
        self.parent_widget.player_action("previous")

    def _on_skip_forward_clicked(self, *args):
        if self._destroyed:
            return
        self.parent_widget.player_action("next")

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

        metadata = self.parent_widget.get_cached_metadata()
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
            self.title_label.set_text(re.sub(r"\r?\n", " ", title))
            self.artist_label.set_text(re.sub(r"\r?\n", " ", artist))
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

        # Request parent to update position
        self.parent_widget.update_position()
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

        self.parent_widget.player_action("seek", seek_sec * 1_000_000)
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

        self._current_player_name = None
        self._cached_metadata = {}
        self._player_valid = False
        self.popup = None
        self._poll_source_id = None
        self._destroyed = False
        self._pending_actions = []

        # Player manager setup
        self.player_manager = Playerctl.PlayerManager.new()
        self._players = {}  # name_str -> player

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

        # Connect manager signals
        self.player_manager.connect("player-vanished", self._on_player_vanished)
        self.player_manager.connect("name-appeared", self._on_name_appeared)

        # Initialize with existing players
        for player_name in self.player_manager.props.player_names:
            GLib.idle_add(self._init_player, player_name)

        self._poll_source_id = GLib.timeout_add(self.poll_interval, self._poll_tick)

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
        self.connect("destroy", self._on_destroy)

    def _on_destroy(self, *args):
        self._destroyed = True
        self._player_valid = False
        if self._poll_source_id is not None:
            GLib.source_remove(self._poll_source_id)
            self._poll_source_id = None
        self._players.clear()
        if self.popup:
            self.popup.destroy()
            self.popup = None

    def _init_player(self, player_name):
        """Initialize a player - called via idle_add to defer from signal context."""
        if self._destroyed:
            return False
        if not isinstance(player_name, Playerctl.PlayerName):
            return False

        name_str = player_name.name
        if name_str in self._players:
            return False

        try:
            player = Playerctl.Player.new_from_name(player_name)
            self.player_manager.manage_player(player)
            self._players[name_str] = player

            # Connect signals - but defer actual property access
            player.connect("metadata", self._on_metadata_signal)
            player.connect("playback-status", self._on_status_signal)

            # If no active player, use this one
            if not self._current_player_name:
                self._current_player_name = name_str
                self._player_valid = True
                # Defer metadata fetch
                GLib.idle_add(self._fetch_metadata)

        except Exception as e:
            print(f"Error initializing player {name_str}: {e}")

        return False

    def _on_name_appeared(self, manager, player_name):
        """New player appeared - defer initialization."""
        if self._destroyed:
            return
        GLib.idle_add(self._init_player, player_name)

    def _on_player_vanished(self, manager, player):
        """Player vanished - find by object identity, don't query the player."""
        if self._destroyed:
            return

        vanished_name = None
        for name, p in list(self._players.items()):
            if p is player:
                vanished_name = name
                break

        if vanished_name:
            del self._players[vanished_name]

            if self._current_player_name == vanished_name:
                self._current_player_name = None
                self._player_valid = False
                self._cached_metadata = {}

                # Switch to another player if available
                if self._players:
                    self._current_player_name = next(iter(self._players.keys()))
                    self._player_valid = True
                    GLib.idle_add(self._fetch_metadata)
                else:
                    GLib.idle_add(self._clear_display)

    def _on_metadata_signal(self, player, metadata):
        """Metadata signal - defer actual property access."""
        if self._destroyed:
            return

        # Check if this is our current player by object identity
        current_player = self._players.get(self._current_player_name)
        if player is not current_player:
            return

        # Defer the actual metadata fetch to avoid issues in signal context
        GLib.idle_add(self._fetch_metadata)

    def _on_status_signal(self, player, status):
        """Playback status signal - status is passed directly, safe to use."""
        if self._destroyed:
            return

        current_player = self._players.get(self._current_player_name)
        if player is not current_player:
            return

        self._cached_metadata["status"] = status

    def _fetch_metadata(self):
        """Fetch metadata from current player - called via idle_add."""
        if self._destroyed or not self._player_valid:
            return False

        player = self._players.get(self._current_player_name)
        if not player:
            self._player_valid = False
            return False

        try:
            metadata = player.props.metadata
            if metadata:
                md = dict(metadata.unpack())
                self._cached_metadata = {
                    "title": md.get("xesam:title", ""),
                    "artist": (md.get("xesam:artist") or [""])[0],
                    "length": md.get("mpris:length", 0),
                    "status": player.props.playback_status,
                    "position": 0,
                }
                # Try to get position
                try:
                    self._cached_metadata["position"] = player.get_position() or 0
                except Exception:
                    pass

                self._update_display()
            else:
                self._cached_metadata = {}
                self._clear_display()

        except Exception as e:
            print(f"Error fetching metadata: {e}")
            # Player might be dead
            self._handle_player_dead()

        return False

    def _handle_player_dead(self):
        """Handle when we detect the player is dead."""
        if self._current_player_name and self._current_player_name in self._players:
            del self._players[self._current_player_name]

        self._current_player_name = None
        self._player_valid = False
        self._cached_metadata = {}

        if self._players:
            self._current_player_name = next(iter(self._players.keys()))
            self._player_valid = True
            GLib.idle_add(self._fetch_metadata)
        else:
            self._clear_display()

    def update_position(self):
        """Update cached position - called by popup for slider updates."""
        if self._destroyed or not self._player_valid:
            return

        player = self._players.get(self._current_player_name)
        if not player:
            return

        try:
            self._cached_metadata["position"] = player.get_position() or 0
        except Exception:
            # Don't crash, just keep old position
            pass

    def _update_display(self):
        """Update the label with cached metadata."""
        if self._destroyed:
            return

        title = self._cached_metadata.get("title", "")
        artist = self._cached_metadata.get("artist", "")
        display_text = f"{title} – {artist}" if artist else title

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

    def get_cached_metadata(self):
        """Get cached metadata for popup."""
        if not self._player_valid:
            return {}
        return self._cached_metadata.copy()

    def player_action(self, action, value=None):
        """Perform a player action safely."""
        if self._destroyed or not self._player_valid:
            return

        player = self._players.get(self._current_player_name)
        if not player:
            return

        try:
            if action == "play_pause":
                status = self._cached_metadata.get("status")
                if status == Playerctl.PlaybackStatus.PLAYING:
                    player.pause()
                else:
                    player.play()
            elif action == "next":
                player.next()
            elif action == "previous":
                player.previous()
            elif action == "seek" and value is not None:
                player.set_position(value)
                player.play()
        except Exception as e:
            print(f"Error performing action {action}: {e}")
            self._handle_player_dead()

    def on_click(self, *_):
        if self.popup:
            self.popup.destroy()
            self.popup = None

        if not self._player_valid:
            return

        self.popup = PlayerctlMenu(self, self, config=self.config)
        self.popup.open()

    def _poll_tick(self):
        """Periodic poll to check state and update position."""
        if self._destroyed:
            return False

        # If no current player but we have players, pick one
        if not self._current_player_name and self._players:
            self._current_player_name = next(iter(self._players.keys()))
            self._player_valid = True
            self._fetch_metadata()

        return True