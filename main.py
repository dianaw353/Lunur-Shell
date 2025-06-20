import setproctitle
from fabric import Application
from fabric.utils import cooldown, exec_shell_command, get_relative_path
from loguru import logger
from gi.repository import Gtk

import utils.functions as helpers
from modules.bar import StatusBar
from modules.launcher import AppLauncher
from utils import APPLICATION_NAME, ExecutableNotFoundError, widget_config


@cooldown(2)
@helpers.run_in_thread
def process_and_apply_css(app: Application):
    if not helpers.executable_exists("sass"):
        raise ExecutableNotFoundError("sass")

    logger.info("[Main] Compiling CSS")
    output = exec_shell_command("sass styles/main.scss dist/main.css --no-source-map")

    if output == "":
        logger.info("[Main] CSS applied")
        app.set_stylesheet_from_file(get_relative_path("dist/main.css"))
    else:
        app.set_stylesheet_from_string("")
        logger.error("[Main] Failed to compile sass!")


if __name__ == "__main__":
    launcher = AppLauncher()
    bar = StatusBar(widget_config)

    windows = [bar, launcher]

    if widget_config.get("notifications", {}).get("enabled", True):
        from services.notifications import NotificationPopup
        notifications = NotificationPopup(widget_config)
        windows.append(notifications)

    app = Application(APPLICATION_NAME, windows=windows)

    icon_theme = Gtk.IconTheme.get_default()
    icons_dir = get_relative_path("./assets/icons/svg/gtk")
    icon_theme.append_search_path(icons_dir)

    process_and_apply_css(app)

    setproctitle.setproctitle(APPLICATION_NAME)

    app.run()
