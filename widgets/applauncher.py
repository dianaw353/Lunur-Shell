from modules.launcher import AppLauncher
from utils.functions import get_distro_icon
from utils.widget_utils import text_icon
from utils.config import widget_config
from utils.widget_settings import BarConfig
from shared.widget_container import ButtonWidget


app_launcher = widget_config["app_launcher"]
icon_size = app_launcher["icon_size"]
app_icon_size = app_launcher["app_icon_size"]

launcher = AppLauncher(app_icon_size=app_icon_size)
launcher.show_all()
launcher.hide()


class AppLauncherButton(ButtonWidget):
    def __init__(self, widget_config: BarConfig, **kwargs):
        super().__init__(
            config=widget_config["app_launcher"],
            name="app-launcher-button",
            **kwargs,
        )

        icon_widget = text_icon(get_distro_icon(), {"size": icon_size})
        self.box.children = [icon_widget]

        self.connect("clicked", self.on_clicked)

    def on_clicked(self, *args):
        if launcher.is_visible():
            launcher.hide()
        else:
            launcher.show_all()
