# widgets/quick_settings/sliders/volume.py

from .slider_row import SliderRow
from services import audio_service
from utils.icons import icons
from utils.widget_utils import get_audio_icon_name


class VolumeSlider(SliderRow):
    """Volume slider with automatic service integration."""

    def __init__(self):
        self.audio = audio_service

        # Get initial volume
        initial_volume = 50
        if self.audio.speaker:
            initial_volume = round(self.audio.speaker.volume)

        super().__init__(
            icon_name=icons["audio"]["volume"]["medium"],
            min_value=0,
            max_value=100,
            initial_value=initial_volume,
            on_change=self._set_volume,
            style_class="volume-slider-row",
        )

        # Connect to audio changes
        self.audio.connect("notify::speaker", self._on_speaker_changed)
        if self.audio.speaker:
            self._connect_speaker_signals()

        self._update_icon(initial_volume)

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
            self.set_value(volume)
            self._update_icon(volume, muted)

    def _update_icon(self, volume: int, muted: bool = False):
        try:
            icon_info = get_audio_icon_name(volume, muted)
            icon_name = icon_info["icon"]
            self.icon.set_from_icon_name(icon_name)
        except Exception:
            pass
