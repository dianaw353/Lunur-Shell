from typing import ClassVar
import gi
from fabric.utils import bulk_connect, remove_handler
from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from fabric.widgets.wayland import WaylandWindow as Window
from gi.repository import GLib, GObject

from services import audio_service
from services.brightness import Brightness
from utils.icons import icons
from utils.widget_utils import (
    create_scale,
    get_audio_icon_name,
    get_brightness_icon_name,
)

gi.require_versions({"GObject": "2.0"})


class GenericOSDContainer(Box):
    """Generic OSD container for audio/brightness."""

    def __init__(self, config: dict, **kwargs):
        is_vertical = config["orientation"] == "vertical"

        super().__init__(
            orientation=config["orientation"],
            spacing=10,
            name="osd-container",
            style_classes="vertical" if is_vertical else "",
            **kwargs,
        )

        self.icon_size = config["icon_size"]
        self.icon = Image(
            icon_name=icons["audio"]["volume"]["medium"],
            icon_size=self.icon_size,
        )

        scale_style = (
            "scale {min-height: 150px; min-width: 11px;}" if is_vertical else ""
        )

        self.scale = create_scale(
            name="osd-scale",
            orientation=config["orientation"],
            h_expand=is_vertical,
            v_expand=is_vertical,
            duration=config["transition_duration"] / 1000,  # seconds
            curve=(0.34, 1.56, 0.64, 1.0),
            inverted=is_vertical,
            style=scale_style,
        )

        self.children = (self.icon, self.scale)

        self.show_level = config["percentage"]
        if self.show_level:
            self.level = Label(name="osd-level", h_align="center", h_expand=True)
            self.add(self.level)

    def update_values(self, value):
        round_value = round(value)
        self.scale.set_value(round_value)
        if self.show_level:
            self.level.set_label(f"{round_value}%")


class AudioOSDContainer(GenericOSDContainer):
    """OSD container for audio volume."""

    __gsignals__: ClassVar = {
        "volume-changed": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self, config: dict, **kwargs):
        super().__init__(config=config, **kwargs)
        self.audio_service = audio_service
        self.previous_volume = None
        self.previous_muted = None

        bulk_connect(
            self.audio_service,
            {
                "notify::speaker": self._on_speaker_changed,
                "changed": self._check_volume_state,
            },
        )

        if self.audio_service.speaker:
            self._bind_and_update(self.audio_service.speaker)

    def _on_speaker_changed(self, *_):
        if speaker := self.audio_service.speaker:
            self._bind_and_update(speaker)

    def _bind_and_update(self, speaker):
        speaker.connect("notify::volume", self._update_volume)
        vol = round(speaker.volume)
        muted = speaker.muted
        self._update_volume_ui(vol, muted)

    def _check_volume_state(self, *_):
        if not self.audio_service.speaker:
            return
        current_muted = self.audio_service.speaker.muted
        current_volume = round(self.audio_service.speaker.volume)
        if self.previous_muted is None or current_muted != self.previous_muted:
            self.previous_muted = current_muted
            self._update_volume_ui(current_volume, current_muted)

    def _update_volume(self, speaker, *_):
        if not self.audio_service.speaker:
            return
        volume = round(speaker.volume)
        is_muted = speaker.muted
        if (
            self.previous_volume is None
            or volume != self.previous_volume
            or is_muted != self.previous_muted
        ):
            self._update_volume_ui(volume, is_muted)

    def _update_volume_ui(self, volume: int, is_muted: bool):
        icon_info = get_audio_icon_name(volume, is_muted)
        self.icon.set_from_icon_name(icon_info["icon"], self.icon_size)

        if is_muted or volume == 0:
            self.scale.add_style_class("muted")
        else:
            self.scale.remove_style_class("muted")

        if volume > 100:
            self.scale.add_style_class("overamplified")
        else:
            self.scale.remove_style_class("overamplified")

        self.update_values(volume)
        self.previous_volume = volume
        self.previous_muted = is_muted
        self.emit("volume-changed")


class BrightnessOSDContainer(GenericOSDContainer):
    """OSD container for screen brightness."""

    __gsignals__: ClassVar = {
        "brightness-changed": (GObject.SignalFlags.RUN_FIRST, None, ())
    }

    def __init__(self, config: dict, **kwargs):
        super().__init__(
            config=config, icon_name=icons["brightness"]["medium"], **kwargs
        )

        self.brightness_service = Brightness()
        self.previous_level = None

        self.brightness_service.brightness_changed.connect(self._on_brightness_changed)

        self._update_brightness_ui(round(self.brightness_service.screen_brightness))

    def _on_brightness_changed(self, service_instance, value, *_):
        level = round((value / service_instance.max_screen) * 100)
        if self.previous_level is None or level != self.previous_level:
            self._update_brightness_ui(level)

    def _update_brightness_ui(self, level: int):
        icon_info = get_brightness_icon_name(level)
        self.icon.set_from_icon_name(icon_info["icon"], self.icon_size)

        self.update_values(level)

        self.previous_level = level
        self.emit("brightness-changed")


class OSDWindow(Window):
    """Top-level OSD window for audio and brightness."""

    def __init__(self, config: dict, **kwargs):
        from .osd import AudioOSDContainer  # keep audio as is

        self.hide_timer_id = None
        self.config = config["osd"]

        self.audio_container = None
        self.brightness_container = None

        if "volume" in self.config.get("osds", []):
            self.audio_container = AudioOSDContainer(config=self.config)
            self.audio_container.connect("volume-changed", self.show_audio)

        if "brightness" in self.config.get("osds", []):
            self.brightness_container = BrightnessOSDContainer(config=self.config)
            self.brightness_container.connect(
                "brightness-changed", self.show_brightness
            )

        self.timeout = self.config["timeout"]

        self.revealer = Revealer(
            name="osd-revealer",
            transition_type=self.config["transition_type"],
            transition_duration=self.config["transition_duration"],
            child_revealed=False,
        )

        if self.audio_container:
            self.revealer.add(self.audio_container)

        anchor_string = self.config["anchor"]

        super().__init__(
            layer="overlay",
            anchor=anchor_string,
            child=self.revealer,
            visible=False,
            pass_through=True,
            name="osd",
            **kwargs,
        )

    def show_audio(self, *_):
        if self.audio_container:
            self._show_container(self.audio_container)

    def show_brightness(self, *_):
        if self.brightness_container:
            self._show_container(self.brightness_container)

    def _show_container(self, container: Box):
        if self.revealer.get_child() != container:
            if self.revealer.get_child():
                self.revealer.remove(self.revealer.get_child())
            self.revealer.add(container)

        self.set_visible(True)

        if self.hide_timer_id is not None:
            remove_handler(self.hide_timer_id)
            self.hide_timer_id = None

        GLib.idle_add(lambda: self.revealer.set_reveal_child(True))
        self.hide_timer_id = GLib.timeout_add(self.timeout, self._hide)

    def _hide(self):
        self.revealer.set_reveal_child(False)
        GLib.timeout_add(self.revealer.get_transition_duration(), self._finalize_hide)
        return False

    def _finalize_hide(self):
        self.set_visible(False)
        self.hide_timer_id = None
        return False
