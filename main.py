import setproctitle
from fabric import Application
from fabric.utils import cooldown, exec_shell_command, get_relative_path, monitor_file
from loguru import logger
from gi.repository import Gtk

import utils.functions as helpers
from modules.bar import StatusBar
from modules.launcher import AppLauncher
from utils import APPLICATION_NAME, APP_CACHE_DIRECTORY, ExecutableNotFoundError, widget_config


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
    helpers.ensure_directory(APP_CACHE_DIRECTORY)
    launcher = AppLauncher()
    bar = StatusBar(widget_config)

    windows = [bar, launcher]

    if widget_config.get("keybinds", {}).get("enabled"):
        from modules.keybinds import KeybindsWidget

        keybinds = KeybindsWidget(widget_config)
        windows.append(keybinds)

    if widget_config["notification"]["enabled"]:
        from modules.notification import NotificationPopup

        notifications = NotificationPopup(widget_config)
        windows.append(notifications)

    if widget_config["general"]["screen_corners"]["enabled"]:
        from modules.corners import ScreenCorners

        screen_corners = ScreenCorners(widget_config)

        windows.append(screen_corners)

    app = Application(APPLICATION_NAME, windows=windows)

    helpers.copy_theme(widget_config["theme"]["name"])

    icon_theme = Gtk.IconTheme.get_default()
    icons_dir = get_relative_path("./assets/icons/svg/gtk")
    icon_theme.append_search_path(icons_dir)

    style_monitor = monitor_file(get_relative_path("./styles"))
    watch_matugen = monitor_file(get_relative_path("./styles/themes/matugen.scss"))
    watch_matugen.connect(
        "changed",
        lambda *args: (
            helpers.copy_theme(widget_config["theme"]["name"]),
            process_and_apply_css(app)
        )
    )
    style_monitor.connect("changed", lambda *args: process_and_apply_css(app)) 
    process_and_apply_css(app)

    setproctitle.setproctitle(APPLICATION_NAME)

    app.run()
