from fabric.utils import exec_shell_command_async, get_relative_path
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window

from shared import ModuleGroup
from utils import HyprlandWithMonitors
from utils.functions import run_in_thread
from utils.widget_utils import lazy_load_widget


class StatusBar(Window):
    """A widget to display the status bar panel."""

    @run_in_thread
    def check_for_bar_updates(self):
        exec_shell_command_async(
            get_relative_path("../assets/scripts/barupdate.sh"),
            lambda _: None,
        )
        return True

    def __init__(self, config, **kwargs):
        self.widgets_list = {
            "app_launcher": "widgets.applauncher.AppLauncherButton",
            "workspaces": "widgets.workspaces.WorkspacesWidget",
            "date_time": "widgets.datetime_menu.DateTimeWidget",
            "battery": "widgets.battery.BatteryWidget",
            "system_tray": "widgets.system_tray.SystemTrayWidget",
            "quick_settings": "widgets.quick_settings.quick_settings.QuickSettingsButtonWidget",
            # Add other widgets here if needed
        }

        options = config.get("general", {})
        layout = self.make_layout(config)

        self.box = CenterBox(
            name="bar-inner",
            start_children=Box(
                spacing=4,
                orientation="h",
                children=layout["left_section"],
            ),
            center_children=Box(
                spacing=4,
                orientation="h",
                children=layout["middle_section"],
            ),
            end_children=Box(
                spacing=4,
                orientation="h",
                children=layout["right_section"],
            ),
        )

        anchor = f"left {options.get('location', 'top')} right"

        super().__init__(
            name="status-bar",
            layer=options.get("layer", "top"),
            anchor=anchor,
            margin=options.get("margin", "6px 6px 0px 6px"),
            pass_through=False,
            monitor=HyprlandWithMonitors().get_current_gdk_monitor_id(),
            exclusivity="auto",
            visible=options.get("visible", True),
            all_visible=False,
            child=self.box,
            **kwargs,
        )

        if options.get("check_updates"):
            self.check_for_bar_updates()

    def make_layout(self, widget_config):
        """Assign widgets to left, middle, right sections based on config."""

        layout = {
            "left_section": widget_config.get("layout", {}).get("start_container", []),
            "middle_section": widget_config.get("layout", {}).get("center_container", []),
            "right_section": widget_config.get("layout", {}).get("end_container", []),
        }

        new_layout = {"left_section": [], "middle_section": [], "right_section": []}

        for section in new_layout:
            for widget_name in layout[section]:
                if widget_name.startswith("@group:"):
                    group_name = widget_name[len("@group:") :]
                    group_config = None

                    if group_name.isdigit():
                        idx = int(group_name)
                        groups = widget_config.get("module_groups", [])
                        if isinstance(groups, list) and 0 <= idx < len(groups):
                            group_config = groups[idx]

                    if group_config:
                        group = ModuleGroup.from_config(
                            group_config,
                            self.widgets_list,
                            bar=self,
                            widget_config=widget_config,
                        )
                        new_layout[section].append(group)
                else:
                    if widget_name in self.widgets_list:
                        widget_class = lazy_load_widget(widget_name, self.widgets_list)
                        # widget_instance = widget_class()
                        try:
                            widget_instance = widget_class(widget_config)
                        except TypeError:
                            widget_instance = widget_class()

                        new_layout[section].append(widget_instance)

        return new_layout
