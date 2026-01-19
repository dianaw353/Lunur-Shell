# widgets/quick_settings/sliders/brightness.py

from .slider_row import SliderRow
from services.brightness import Brightness
import utils.functions as helpers
from utils.icons import icons
from utils.widget_utils import get_brightness_icon_name


class BrightnessSlider(SliderRow):
    """Brightness slider with automatic service integration."""

    def __init__(self):
        self.brightness_service = Brightness()
        self._updating = False
        self._internal_change = False

        # Get initial brightness percent
        try:
            current = self.brightness_service.screen_brightness
            max_brightness = self.brightness_service.max_screen
            initial_percent = helpers.convert_to_percent(current, max_brightness)
        except Exception:
            initial_percent = 50

        # Get initial icon
        try:
            icon_info = get_brightness_icon_name(initial_percent)
            initial_icon = icon_info.get("icon", icons["brightness"]["indicator"])
        except Exception:
            initial_icon = icons["brightness"]["indicator"]

        # The minimum value is rather hacky but it had to be done.
        super().__init__(
            icon_name=initial_icon,
            min_value=0.1,
            max_value=100,
            initial_value=initial_percent,
            on_change=self._set_brightness,
            style_class="brightness-slider-row",
        )

        self.brightness_service.connect(
            "brightness_changed", self._on_brightness_changed
        )

    def _set_brightness(self, value: float):
        if self._updating or self._internal_change:
            return

        try:
            self._updating = True
            max_brightness = self.brightness_service.max_screen
            actual_value = int((value / 100) * max_brightness)
            self.brightness_service.screen_brightness = actual_value
            self._update_icon(value)
        except Exception as e:
            print(f"[BrightnessSlider] Error setting brightness: {e}")
        finally:
            self._updating = False

    def _on_brightness_changed(self, *_):
        if self._updating:
            return

        try:
            self._internal_change = True
            current = self.brightness_service.screen_brightness
            max_brightness = self.brightness_service.max_screen
            percent = helpers.convert_to_percent(current, max_brightness)
            self.set_value(percent)
            self._update_icon(percent)
        except Exception as e:
            print(f"[BrightnessSlider] Error updating from service: {e}")
        finally:
            self._internal_change = False

    def _update_icon(self, percent: float):
        try:
            icon_info = get_brightness_icon_name(percent)
            icon_name = icon_info.get("icon", icons["brightness"]["indicator"])
            self.set_icon(icon_name)
        except Exception:
            pass
