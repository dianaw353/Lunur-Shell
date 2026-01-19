import time
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.wayland import WaylandWindow as Window

from shared.widget_container import ToggleableWidget
from shared.module_group import ModuleGroup
from shared.collapsible_groups import CollapsibleGroups
from utils.monitors import HyprlandWithMonitors
from utils.widget_utils import lazy_load_widget
from modules.corners import SideCorner
from fabric.utils import logger


class StatusBar(Window, ToggleableWidget):
    """A widget to display the status bar panel."""

    def __init__(self, config, **kwargs):
        self.widgets_list = {
            "app_launcher": "widgets.applauncher.AppLauncherButton",
            "workspaces": "widgets.workspaces.WorkspacesWidget",
            "date_time": "widgets.datetime_menu.DateTimeWidget",
            "battery": "widgets.battery.BatteryWidget",
            "system_tray": "widgets.system_tray.SystemTrayWidget",
            "quick_settings": "widgets.quick_settings.quick_settings.QuickSettingsButtonWidget",
            "window_title": "widgets.window_title.WindowTitleWidget",
            "hyprpicker": "widgets.hyprpicker.HyprPickerButton",
            "power_profiles": "widgets.power_profile.PowerProfileButton",
            "emoji_picker": "widgets.emoji_picker.EmojiPickerWidget",
            "cliphist": "widgets.cliphist.ClipHistoryWidget",
            "playerctl": "widgets.playerctl.PlayerctlWidget",
            "sleep": "widgets.power_menu.SleepWidget",
            "reboot": "widgets.power_menu.RebootWidget",
            "logout": "widgets.power_menu.LogoutWidget",
            "shutdown": "widgets.power_menu.ShutdownWidget",
            "screenshot": "widgets.screenshot.ScreenShotWidget",
            "recorder": "widgets.recorder.RecorderWidget",
        }

        self.debug = config.get("general", {}).get("debug", False)
        options = config["general"]

        # Store bar location for corner mirroring
        self.bar_location = options.get("location", "top")

        layout = self.make_layout(config)

        # Create corners with shared size constant
        corner_size = 20
        self.center_corner_left = self._make_corner(
            "corner-left", "top-right", "start", corner_size
        )
        self.center_corner_right = self._make_corner(
            "corner-right", "top-left", "end", corner_size
        )
        self.start_corner_right = self._make_corner(
            "corner-right", "top-left", "end", corner_size
        )
        self.end_corner_left = self._make_corner(
            "corner-left", "top-right", "start", corner_size
        )

        # Create section boxes with location class
        location_class = f"location-{self.bar_location}"

        start_box = Box(
            name="start",
            spacing=4,
            orientation="h",
            children=layout["left_section"],
        )
        start_box.add_style_class(location_class)

        center_box = Box(
            name="center",
            spacing=4,
            orientation="h",
            children=layout["middle_section"],
        )
        center_box.add_style_class(location_class)

        end_box = Box(
            name="end",
            spacing=4,
            orientation="h",
            children=layout["right_section"],
        )
        end_box.add_style_class(location_class)

        self.box = CenterBox(
            name="panel-inner",
            start_children=Box(
                name="start-wrapper",
                spacing=4,
                orientation="h",
                children=[
                    start_box,
                    self.start_corner_right,
                ],
            ),
            center_children=Box(
                name="center-wrapper",
                spacing=4,
                orientation="h",
                children=[
                    self.center_corner_left,
                    center_box,
                    self.center_corner_right,
                ],
            ),
            end_children=Box(
                name="end-wrapper",
                spacing=4,
                orientation="h",
                children=[
                    self.end_corner_left,
                    end_box,
                ],
            ),
        )

        self.box.add_style_class(location_class)

        super().__init__(
            name="panel",
            layer=options["layer"],
            anchor=f"left {options['location']} right",
            pass_through=False,
            monitor=HyprlandWithMonitors().get_current_gdk_monitor_id(),
            exclusivity="auto",
            visible=options.get("visible", True),
            all_visible=False,
            child=self.box,
            **kwargs,
        )

        self.add_style_class(location_class)

    def _make_corner(self, name, corner_type, h_align, size):
        """Create a corner box, automatically mirrored for bottom bar."""
        if self.bar_location == "bottom":
            if corner_type.startswith("top-"):
                corner_type = "bottom-" + corner_type[4:]

        corner_widget = SideCorner(corner_type, size)
        spacer = Box(v_expand=True)

        if self.bar_location == "bottom":
            children = [spacer, corner_widget]
        else:
            children = [corner_widget, spacer]

        return Box(
            name=name,
            orientation="v",
            h_align=h_align,
            children=children,
        )

    def _get_widget_class(self, name):
        """Load widget class on demand."""
        return lazy_load_widget(name, self.widgets_list)

    def _create_widget(self, widget_name, widget_config):
        """Create a single widget instance with timing."""
        if widget_name not in self.widgets_list:
            return None

        cls = self._get_widget_class(widget_name)
        start = time.perf_counter()
        widget_instance = cls(widget_config)

        if self.debug:
            logger.info(f"{widget_name}: {(time.perf_counter() - start) * 1000:.1f}ms")

        return widget_instance

    def _create_collapsible_group(self, idx, widget_config):
        """Create a collapsible group with optimized widget loading."""
        groups = widget_config.get("collapsible_groups", [])
        if not (0 <= idx < len(groups)):
            return None

        group_start = time.perf_counter()
        group_config = groups[idx]

        # Create all child widgets
        child_widgets = []
        for wname in group_config.get("widgets", []):
            widget = self._create_widget(wname, widget_config)
            if widget:
                child_widgets.append(widget)

        # Create collapsible group
        collapsible = CollapsibleGroups(
            collapsed_icon=group_config.get("collapsed_icon"),
            child_widgets=child_widgets,
            slide_direction=group_config.get("slide_direction"),
            transition_duration=group_config.get("transition_duration"),
            spacing=group_config.get("spacing"),
            tooltip=group_config.get("tooltip"),
            icon_size=group_config.get("icon_size"),
        )

        if self.debug:
            logger.info(
                f"CollapsibleGroup {idx}: {(time.perf_counter() - group_start) * 1000:.1f}ms"
            )

        return collapsible

    def _create_module_group(self, idx, widget_config):
        """Create a module group."""
        groups = widget_config.get("module_groups", [])
        if not (0 <= idx < len(groups)):
            return None

        group_config = groups[idx]
        group_start = time.perf_counter()

        children_widgets = []
        for widget_name in group_config.get("widgets", []):
            widget = self._create_widget(widget_name, widget_config)
            if widget:
                children_widgets.append(widget)

        group = ModuleGroup(
            children=children_widgets,
            spacing=group_config.get("spacing", 4),
            name=f"module-group-{idx}",
        )

        if self.debug:
            logger.info(
                f"ModuleGroup {idx}: {(time.perf_counter() - group_start) * 1000:.1f}ms"
            )

        return group

    def make_layout(self, widget_config):
        """Build layout with on-demand widget loading."""
        layout = {
            "left_section": widget_config.get("layout", {}).get("start_container", []),
            "middle_section": widget_config.get("layout", {}).get(
                "center_container", []
            ),
            "right_section": widget_config.get("layout", {}).get("end_container", []),
        }

        new_layout = {"left_section": [], "middle_section": [], "right_section": []}

        for section, widget_names in layout.items():
            section_widgets = new_layout[section]

            for widget_name in widget_names:
                widget = None

                # Module group
                if widget_name.startswith("@group:"):
                    group_idx = widget_name[7:]
                    if group_idx.isdigit():
                        widget = self._create_module_group(
                            int(group_idx), widget_config
                        )

                # Collapsible group
                elif widget_name.startswith("@collapsible_group:"):
                    group_idx = widget_name[19:]
                    if group_idx.isdigit():
                        widget = self._create_collapsible_group(
                            int(group_idx), widget_config
                        )

                # Regular widget
                else:
                    widget = self._create_widget(widget_name, widget_config)

                if widget:
                    section_widgets.append(widget)

        return new_layout
