from fabric.hyprland.widgets import WorkspaceButton as WsButton, HyprlandWorkspaces
from shared.widget_container import BoxWidget
from utils.widget_settings import BarConfig
from utils.functions import unique_list
from utils.widget_utils import setup_cursor_hover


class WorkspaceButton(WsButton):
    """A button to represent a workspace."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        setup_cursor_hover(self)


class WorkspacesWidget(BoxWidget):
    """A widget to display the current workspaces."""

    def __init__(self, widget_config: BarConfig, **kwargs):
        super().__init__(name="workspaces", **kwargs)

        config = widget_config["workspaces"]

        ignored_ws = [int(x) for x in unique_list(config.get("ignored", []))]
        default_format = config.get("default_label_format", "{id}")
        icon_map = config.get("icon_map", {})
        count = config.get("count", 10)
        hide_unoccupied = config.get("hide_unoccupied", True)
        reverse_scroll = config.get("reverse_scroll", False)
        empty_scroll = config.get("empty_scroll", False)

        def create_workspace_label(ws_id: int) -> str:
            return icon_map.get(str(ws_id), default_format.format(id=ws_id))

        def setup_button_empty_state(button: WorkspaceButton) -> WorkspaceButton:
            def update_empty_state(*_):
                if button.get_empty():
                    button.add_style_class("unoccupied")
                else:
                    button.remove_style_class("unoccupied")

            button.connect("notify::empty", update_empty_state)
            update_empty_state()
            return button

        # Generate pre-set buttons if showing unoccupied workspaces
        buttons = (
            None
            if hide_unoccupied
            else [
                setup_button_empty_state(
                    WorkspaceButton(id=i, label=create_workspace_label(i))
                )
                for i in range(1, count + 1)
                if i not in ignored_ws
            ]
        )

        self.workspace = HyprlandWorkspaces(
            name="workspaces",
            spacing=4,
            count=count,
            hide_unoccupied=hide_unoccupied,
            buttons=buttons,
            buttons_factory=lambda ws_id: setup_button_empty_state(
                WorkspaceButton(
                    id=ws_id,
                    label=create_workspace_label(ws_id),
                    visible=ws_id not in ignored_ws,
                )
            ),
            invert_scroll=reverse_scroll,
            empty_scroll=empty_scroll,
        )

        self.children = self.workspace
