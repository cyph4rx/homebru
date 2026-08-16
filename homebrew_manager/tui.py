from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.widgets import Button, DataTable, Input, Label, Static

from .api import AgentClient, AgentError, ServiceAction
from .config import ConfigError, ServerConfig, save_config
from .formatting import clamp_percent, format_bytes, format_uptime
from .local_setup import (
    create_local_custom_server,
    create_local_template_server,
    default_server_directory,
    ensure_local_agent,
)


ASCII_LOGO = """ ██╗  ██╗ ██████╗ ███╗   ███╗███████╗██████╗ ██████╗ ██╗   ██╗
 ██║  ██║██╔═══██╗████╗ ████║██╔════╝██╔══██╗██╔══██╗██║   ██║
 ███████║██║   ██║██╔████╔██║█████╗  ██████╔╝██████╔╝██║   ██║
 ██╔══██║██║   ██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██╗██║   ██║
 ██║  ██║╚██████╔╝██║ ╚═╝ ██║███████╗██████╔╝██║  ██║╚██████╔╝
 ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝"""

@dataclass(frozen=True, slots=True)
class TemplateForm:
    title: str
    default_name: str
    option_label: str
    default_option: str
    option_placeholder: str
    summary: str
    instructions: str


@dataclass(frozen=True, slots=True)
class AutocompleteOption:
    value: str
    label: str
    description: str


SERVER_TEMPLATES = {
    "discord-bot": TemplateForm(
        title="Discord bot",
        default_name="discord-bot",
        option_label="Discord token",
        default_option="",
        option_placeholder="Can be left blank and added later",
        summary="Creates a discord.py bot with /ping and /hello commands.",
        instructions="The token is optional now. If blank, add it to .env before starting the bot.",
    ),
    "minecraft-java": TemplateForm(
        title="Minecraft Java server",
        default_name="minecraft-server",
        option_label="Memory (MB)",
        default_option="2048",
        option_placeholder="2048",
        summary="Creates Minecraft configuration and registers the Java server.",
        instructions="After creation, add the official server.jar and accept the EULA as explained in README.txt.",
    ),
    "python-http": TemplateForm(
        title="Python web server",
        default_name="python-server",
        option_label="Port",
        default_option="8000",
        option_placeholder="8000",
        summary="Creates a small web server using only Python's standard library.",
        instructions="Edit files in the generated public folder, then start the server from Homebru.",
    ),
    "node-http": TemplateForm(
        title="Node.js web server",
        default_name="node-server",
        option_label="Port",
        default_option="3000",
        option_placeholder="3000",
        summary="Creates a dependency-free Node.js HTTP server.",
        instructions="Node.js must be installed and available as the node command before you start it.",
    ),
}

TEMPLATE_BUTTONS = {
    "template-discord": "discord-bot",
    "template-minecraft": "minecraft-java",
    "template-python": "python-http",
    "template-node": "node-http",
}

NAVIGATION_PANEL_IDS = (
    "#welcome-panel",
    "#template-picker-panel",
    "#local-setup-panel",
    "#custom-setup-panel",
    "#connection-panel",
)

COMMAND_AUTOCOMPLETE_OPTIONS = (
    AutocompleteOption("/start ", "/start [service]", "Start a service"),
    AutocompleteOption("/stop ", "/stop [service]", "Stop a service"),
    AutocompleteOption("/restart ", "/restart [service]", "Restart a service"),
    AutocompleteOption("/refresh", "/refresh", "Refresh server data"),
    AutocompleteOption("/home", "/home", "Return to the home screen"),
    AutocompleteOption("/setup", "/setup", "Browse server templates"),
    AutocompleteOption("/custom", "/custom", "Create a server from scratch"),
    AutocompleteOption("/connect", "/connect", "Change server connection"),
    AutocompleteOption("/help", "/help", "Show available commands"),
    AutocompleteOption("/quit", "/quit", "Exit Homebru"),
)
SERVICE_COMMANDS = frozenset({"/start", "/stop", "/restart"})
MAX_VISIBLE_AUTOCOMPLETE_OPTIONS = 2

HELP_TEXT = (
    "Commands: /start [service]  /stop [service]  /restart [service]  "
    "/refresh  /home  /setup  /custom  /connect  /quit"
)


def _autocomplete_options(input_value: str, service_names: list[str]) -> list[AutocompleteOption]:
    typed_value = input_value.lstrip()
    if not typed_value.startswith("/"):
        return []

    command, separator, argument = typed_value.partition(" ")
    command = command.casefold()
    if separator:
        if command not in SERVICE_COMMANDS:
            return []
        service_prefix = argument.lstrip().casefold()
        action = command.removeprefix("/").title()
        return [
            AutocompleteOption(f"{command} {service_name}", service_name, f"{action} service")
            for service_name in dict.fromkeys(service_names)
            if service_name.casefold().startswith(service_prefix)
        ]

    command_prefix = typed_value.casefold()
    return [
        option
        for option in COMMAND_AUTOCOMPLETE_OPTIONS
        if option.value.rstrip().casefold().startswith(command_prefix)
    ]


def _format_percent_meter(percent: object, width: int = 26) -> str:
    value = clamp_percent(percent)
    complete = round(value / 100 * width)
    bar = "=" * complete
    empty = "-" * (width - complete)
    color = "#CC0000" if value >= 85 else "#E5E5E5"
    return f"[#777777][[/][{color}]{bar}[/][#444444]{empty}[/][#777777]][/] {value:3.0f}%"


def _service_status_label(active_state: str) -> str:
    if active_state == "active":
        return "[#E5E5E5]Running[/]"
    if active_state == "failed":
        return "[#CC0000]Failed[/]"
    return "[#808080]Stopped[/]"


def _format_hardware_lines(stats: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for disk in stats.get("disks") or []:
        mountpoint = str(disk.get("mountpoint", "disk"))
        usage = f"{format_bytes(disk.get('used'))} / {format_bytes(disk.get('total'))}"
        meter = _format_percent_meter(disk.get("percent"), 14)
        lines.append(f"[b]{mountpoint}[/]  {meter}  [#808080]{usage}[/]")
    for gpu in stats.get("gpus") or []:
        name = str(gpu.get("name", "GPU"))
        temperature = gpu.get("temperature_c", "—")
        meter = _format_percent_meter(gpu.get("utilization_percent"), 14)
        lines.append(f"[b]{name}[/]  {meter}  [#808080]{temperature}°C[/]")
    if not lines:
        lines.append("[#808080]No mounted disks or supported NVIDIA GPU reported.[/]")
    return lines


def _input_row(label: str, input_widget: Input, *, label_id: str | None = None) -> Horizontal:
    return Horizontal(
        Label(label, id=label_id, classes="connection-label"),
        input_widget,
        classes="connection-row",
    )


class MetricCard(Static):
    def __init__(self, title: str, *, id: str) -> None:
        super().__init__(id=id, classes="metric-card")
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="eyebrow")
        yield Static("[#808080]Waiting for data...[/]", classes="metric-value")
        yield Static("", classes="metric-detail")

    def set_value(self, percent: object, detail: str) -> None:
        self.query_one(".metric-value", Static).update(_format_percent_meter(percent))
        self.query_one(".metric-detail", Static).update(detail)


class HomebruApp(App[None]):
    TITLE = "Homebru"
    SUB_TITLE = "Server manager made easy for PCs/Laptops."
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    $paper: #000000;
    $ink: #E5E5E5;
    $muted: #808080;
    $line: #404040;
    $accent: #FFFFFF;
    $bad: #CC0000;

    Screen { background: $paper; color: $ink; }
    #app-shell { height: 100%; padding: 1 3 0 3; background: $paper; }
    #masthead { height: 10; padding: 0; align-horizontal: center; }
    #brand { width: 100%; height: 9; align-horizontal: center; }
    #brand-logo {
        width: 100%;
        height: 6;
        color: $accent;
        text-style: bold;
        content-align: center middle;
        text-align: center;
    }
    #brand-subtitle {
        width: 100%;
        height: 2;
        margin-top: 1;
        color: $muted;
        content-align: center middle;
        text-align: center;
    }
    #connection-state {
        width: 100%;
        height: 1;
        padding: 0 1;
        content-align: center top;
        background: $paper;
        color: $muted;
    }
    #connection-state.connected { color: $ink; }
    #connection-state.error { color: $bad; }
    .hidden { display: none; }
    #welcome-panel, #template-picker-panel, #local-setup-panel, #custom-setup-panel, #connection-panel {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: solid $line;
        background: $paper;
    }
    #welcome-heading, #template-picker-heading, #local-setup-heading, #custom-setup-heading, #connection-heading {
        height: 2;
        color: $accent;
        text-style: bold;
        content-align: center middle;
        text-align: center;
    }
    #welcome-note, #template-picker-note, #local-setup-note,
    #custom-setup-note, #connection-note {
        height: 2;
        color: $muted;
        content-align: center middle;
        text-align: center;
    }
    #welcome-server-actions, #welcome-setup-actions, #template-picker-actions,
    #local-setup-actions, #custom-setup-actions, #connection-actions, #service-actions {
        height: 3;
        align-horizontal: center;
    }
    .template-row { height: 3; align-horizontal: center; }
    .setup-instructions { height: 3; color: $muted; }
    .connection-row { height: 3; }
    .connection-label { width: 14; height: 1; color: $muted; content-align: left middle; }
    .connection-input {
        width: 1fr;
        height: 1;
        padding: 0 1;
        border: none;
        background: $paper;
        color: $ink;
    }
    .connection-input:focus { border: none; background: #151515; }
    #connection-error { height: 1; color: $bad; }
    #local-setup-error, #custom-setup-error { height: 1; color: $bad; }
    #content-scroll { height: 1fr; scrollbar-color: #505050; scrollbar-background: $paper; }
    #summary { height: auto; layout: grid; grid-size: 1 3; grid-gutter: 0; margin: 0 0 1 0; }
    .metric-card {
        layout: horizontal;
        height: 3;
        padding: 0 1;
        background: $paper;
        border: solid $line;
    }
    .eyebrow { width: 18; height: 1; color: $muted; text-style: bold; content-align: left middle; }
    .metric-value { width: 42; height: 1; margin: 0; color: $ink; content-align: left middle; }
    .metric-detail { width: 1fr; height: 1; color: $muted; content-align: right middle; }
    .panel { margin: 0 0 1 0; padding: 0 1; background: $paper; border: solid $line; }
    #hardware-panel { height: auto; min-height: 4; }
    .panel-heading { height: 1; color: $muted; text-style: bold; }
    #hardware-details { height: auto; color: $muted; }
    #services-panel { height: auto; min-height: 10; padding-bottom: 0; }
    #service-table { height: auto; min-height: 5; max-height: 14; background: $paper; }
    DataTable > .datatable--header { background: $paper; color: $muted; text-style: bold; }
    DataTable > .datatable--cursor { background: #202020; color: $ink; }
    #service-actions { padding-top: 0; }
    Button { min-width: 12; height: 1; margin-left: 1; background: $paper; color: $muted; border: none; }
    Button:hover { background: #202020; color: $ink; }
    #stop { color: $bad; }
    #connect { color: $ink; }
    #composer-wrap { height: 3; padding: 0 1; background: $paper; border: solid $line; }
    #prompt { width: 3; height: 1; content-align: left middle; color: $ink; }
    #command { width: 1fr; height: 1; border: none; background: $paper; color: $ink; padding: 0; }
    #command:focus { border: none; }
    #hint { width: auto; height: 1; content-align: right middle; color: $muted; }
    #command-suggestions {
        height: auto;
        max-height: 4;
        padding: 0 1;
        background: $paper;
        color: $muted;
        border: solid $line;
    }
    #message-line { height: 1; padding: 0 1; color: $muted; }
    #message-line.error { color: $bad; }
    #message-line.active { color: $ink; }
    """

    BINDINGS = [
        Binding("ctrl+r", "refresh", "Refresh", show=False),
        Binding("ctrl+c", "quit", "Quit", show=False, priority=True),
        Binding("escape", "focus_command", "Command", show=False),
    ]

    def __init__(self, config: ServerConfig | None, config_path: Path, save_connection: bool = True) -> None:
        super().__init__()
        self.theme = "textual-dark"
        self.config = config
        self.config_path = config_path
        self.save_connection = save_connection
        self.client: AgentClient | None = None
        self.service_names: list[str] = []
        self.refresh_timer = None
        self.refresh_in_progress = False
        self.setup_in_progress = False
        self.selected_template_id = "discord-bot"
        self.dashboard_open = False
        self.command_suggestions: list[AutocompleteOption] = []
        self.selected_suggestion_index = 0

    def compose(self) -> ComposeResult:
        yield Vertical(
            self._build_masthead(),
            self._build_home_panel(),
            self._build_template_picker(),
            self._build_template_form(),
            self._build_custom_form(),
            self._build_connection_form(),
            self._build_dashboard(),
            Static("Ready", id="message-line"),
            Static("", id="command-suggestions", classes="hidden"),
            self._build_command_bar(),
            id="app-shell",
        )

    def _build_masthead(self) -> Vertical:
        brand = Vertical(
            Static(ASCII_LOGO, id="brand-logo", markup=False),
            Static("Server manager made easy for PCs.\nType /help to list commands.", id="brand-subtitle"),
            id="brand",
        )
        connection_label = "Saved server" if self.config else "Not connected"
        return Vertical(brand, Static(connection_label, id="connection-state"), id="masthead")

    def _build_home_panel(self) -> Vertical:
        saved_server = (
            f"Saved server: {self.config.host}:{self.config.port}"
            if self.config
            else "Choose what you want to do on this computer."
        )
        server_actions = []
        if self.config:
            server_actions.append(Button("Open saved server", id="open-dashboard"))
        server_actions.append(Button("Connect to an existing server", id="connect-existing"))
        return Vertical(
            Static("Home", id="welcome-heading"),
            Static(saved_server, id="welcome-note"),
            Horizontal(*server_actions, id="welcome-server-actions"),
            Horizontal(
                Button("Server templates", id="setup-templates"),
                Button("Create from scratch", id="setup-custom"),
                id="welcome-setup-actions",
            ),
            id="welcome-panel",
        )

    def _build_template_picker(self) -> Vertical:
        return Vertical(
            Static("Server templates", id="template-picker-heading"),
            Static(
                "Choose a starter. Homebru creates the files and registers it as a managed server.",
                id="template-picker-note",
            ),
            Horizontal(
                Button("Discord bot", id="template-discord"),
                Button("Minecraft Java", id="template-minecraft"),
                classes="template-row",
            ),
            Horizontal(
                Button("Python web server", id="template-python"),
                Button("Node.js web server", id="template-node"),
                classes="template-row",
            ),
            Horizontal(Button("Back", id="close-template-picker"), id="template-picker-actions"),
            id="template-picker-panel",
            classes="hidden",
        )

    def _build_template_form(self) -> Vertical:
        return Vertical(
            Static("Server template", id="local-setup-heading"),
            Static("Choose the template settings.", id="local-setup-note"),
            _input_row(
                "Server name",
                Input(value="discord-bot", id="local-name", classes="connection-input local-setup-input"),
            ),
            _input_row(
                "Server folder",
                Input(
                    value=str(default_server_directory()),
                    id="local-directory",
                    classes="connection-input local-setup-input",
                ),
            ),
            _input_row(
                "Template option",
                Input(id="template-option", classes="connection-input local-setup-input"),
                label_id="template-option-label",
            ),
            Static("", id="template-instructions", classes="setup-instructions"),
            Static("", id="local-setup-error"),
            Horizontal(
                Button("Back", id="close-local-setup"),
                Button("Create template", id="create-local-server"),
                id="local-setup-actions",
            ),
            id="local-setup-panel",
            classes="hidden",
        )

    def _build_custom_form(self) -> Vertical:
        return Vertical(
            Static("Create a server from scratch", id="custom-setup-heading"),
            Static(
                "Register an existing server program or start a new project without a template.",
                id="custom-setup-note",
            ),
            Static(
                "Choose its working folder and enter the command used to start it. Quote paths containing spaces.\n"
                "Examples: python server.py | node server.js | java -jar server.jar nogui",
                classes="setup-instructions",
            ),
            _input_row(
                "Server name",
                Input(value="custom-server", id="custom-name", classes="connection-input custom-setup-input"),
            ),
            _input_row(
                "Server folder",
                Input(
                    value=str(default_server_directory("custom-server")),
                    id="custom-directory",
                    classes="connection-input custom-setup-input",
                ),
            ),
            _input_row(
                "Start command",
                Input(
                    placeholder="python server.py",
                    id="custom-command",
                    classes="connection-input custom-setup-input",
                ),
            ),
            _input_row(
                "Description",
                Input(
                    value="Custom server",
                    id="custom-description",
                    classes="connection-input custom-setup-input",
                ),
            ),
            Static("", id="custom-setup-error"),
            Horizontal(
                Button("Back", id="close-custom-setup"),
                Button("Register server", id="create-custom-server"),
                id="custom-setup-actions",
            ),
            id="custom-setup-panel",
            classes="hidden",
        )

    def _build_connection_form(self) -> Vertical:
        saved_host = self.config.host if self.config else ""
        saved_port = str(self.config.port if self.config else 8420)
        saved_scheme = self.config.scheme if self.config else "http"
        return Vertical(
            Static("Connection", id="connection-heading"),
            Static(
                "Enter the agent address and token. The token is not displayed after it is saved.",
                id="connection-note",
            ),
            _input_row(
                "Host or IP",
                Input(value=saved_host, placeholder="192.168.1.50", id="host", classes="connection-input"),
            ),
            _input_row(
                "Port",
                Input(
                    value=saved_port,
                    placeholder="8420",
                    type="integer",
                    id="port",
                    classes="connection-input",
                ),
            ),
            _input_row(
                "Token",
                Input(placeholder="paste agent token", password=True, id="token", classes="connection-input"),
            ),
            _input_row(
                "Protocol",
                Input(
                    value=saved_scheme,
                    placeholder="http or https",
                    id="scheme",
                    classes="connection-input",
                ),
            ),
            Static("", id="connection-error"),
            Horizontal(
                Button("Close", id="close-connection"),
                Button("Connect", id="connect"),
                id="connection-actions",
            ),
            id="connection-panel",
            classes="hidden",
        )

    def _build_dashboard(self) -> VerticalScroll:
        summary = Container(
            MetricCard("CPU", id="cpu-card"),
            MetricCard("Memory", id="memory-card"),
            MetricCard("Uptime", id="uptime-card"),
            id="summary",
        )
        hardware = Vertical(
            Static("Storage and graphics", classes="panel-heading"),
            Static("[#808080]Waiting for data...[/]", id="hardware-details"),
            classes="panel",
            id="hardware-panel",
        )
        services = Vertical(
            Static("Services", classes="panel-heading"),
            DataTable(id="service-table", cursor_type="row", zebra_stripes=True),
            Horizontal(
                Button("Home", id="home"),
                Button("Start", id="start"),
                Button("Stop", id="stop"),
                Button("Restart", id="restart"),
                Button("Refresh", id="refresh"),
                id="service-actions",
            ),
            classes="panel",
            id="services-panel",
        )
        return VerticalScroll(summary, hardware, services, id="content-scroll", classes="hidden")

    def _build_command_bar(self) -> Horizontal:
        return Horizontal(
            Static(">", id="prompt"),
            Input(placeholder="Type / to browse commands", id="command"),
            Static("Tab: complete | ↑↓: choose | Ctrl+C: quit", id="hint"),
            id="composer-wrap",
        )

    def on_mount(self) -> None:
        table = self.query_one("#service-table", DataTable)
        table.add_columns("Status", "Service", "State", "Startup", "Description")
        self._show_home()

    async def on_unmount(self) -> None:
        if self.client:
            await self.client.close()

    def _pause_dashboard(self) -> None:
        self.dashboard_open = False
        if self.refresh_timer:
            self.refresh_timer.stop()
            self.refresh_timer = None
        old_client = self.client
        self.client = None
        if old_client:
            asyncio.create_task(old_client.close())

    def _hide_navigation_panels(self) -> None:
        for panel_id in NAVIGATION_PANEL_IDS:
            self.query_one(panel_id, Vertical).add_class("hidden")

    def _display_panel(self, panel_id: str, focus_id: str, message: str) -> None:
        self._pause_dashboard()
        self._hide_navigation_panels()
        self.query_one("#content-scroll", VerticalScroll).add_class("hidden")
        self.query_one(panel_id, Vertical).remove_class("hidden")
        self._set_message(message, "active")
        self.query_one(focus_id).focus()

    def _show_connection(self) -> None:
        if self.config:
            self.query_one("#host", Input).value = self.config.host
            self.query_one("#port", Input).value = str(self.config.port)
            self.query_one("#scheme", Input).value = self.config.scheme
            self.query_one("#token", Input).value = ""
        self.query_one("#connection-error", Static).update("")
        self._display_panel(
            "#connection-panel",
            "#host",
            "Edit the connection. Leave the token blank to keep the saved token.",
        )

    def _show_home(self) -> None:
        if self.config:
            self._set_connection(f"Saved: {self.config.host}")
            focus_id = "#open-dashboard"
            message = "Choose Open saved server to load its dashboard."
        else:
            self._set_connection("Not connected")
            focus_id = "#setup-templates"
            message = "Choose how you want to set up Homebru."
        self._display_panel("#welcome-panel", focus_id, message)

    def _show_template_picker(self) -> None:
        self._display_panel("#template-picker-panel", "#template-discord", "Choose a server template.")

    def _show_template_form(self, template_id: str | None = None) -> None:
        if template_id is not None:
            self.selected_template_id = template_id
        template = SERVER_TEMPLATES[self.selected_template_id]
        self.query_one("#local-setup-heading", Static).update(template.title)
        self.query_one("#local-setup-note", Static).update(template.summary)
        self.query_one("#local-name", Input).value = template.default_name
        self.query_one("#local-directory", Input).value = str(default_server_directory(template.default_name))
        option = self.query_one("#template-option", Input)
        option.value = template.default_option
        option.placeholder = template.option_placeholder
        option.password = self.selected_template_id == "discord-bot"
        self.query_one("#template-option-label", Label).update(template.option_label)
        self.query_one("#template-instructions", Static).update(template.instructions)
        self.query_one("#local-setup-error", Static).update("")
        self._display_panel(
            "#local-setup-panel",
            "#local-name",
            f"Configure the {template.title} template.",
        )

    def _close_template_form(self) -> None:
        self._show_template_picker()

    def _show_custom_form(self) -> None:
        self.query_one("#custom-setup-error", Static).update("")
        self._display_panel(
            "#custom-setup-panel",
            "#custom-name",
            "Enter the folder and exact command that starts your server.",
        )

    def _set_setup_form_disabled(
        self,
        input_selector: str,
        button_ids: tuple[str, ...],
        disabled: bool,
    ) -> None:
        for input_widget in self.query(input_selector):
            input_widget.disabled = disabled
        for button_id in button_ids:
            self.query_one(button_id, Button).disabled = disabled

    @work(group="local-setup")
    async def _create_server_from_template(self) -> None:
        server_name = self.query_one("#local-name", Input).value.strip()
        project_directory_text = self.query_one("#local-directory", Input).value.strip()
        template_option = self.query_one("#template-option", Input).value
        error_message = self.query_one("#local-setup-error", Static)
        if not server_name or not project_directory_text:
            error_message.update("Error: server name and folder are required.")
            self._set_message("The local server details are incomplete.", "error")
            return
        if self.setup_in_progress:
            return
        self.setup_in_progress = True

        form_buttons = ("#close-local-setup", "#create-local-server")
        self._set_setup_form_disabled(".local-setup-input", form_buttons, True)
        error_message.update("")
        self._set_message("Creating the server and installing dependencies. This can take a few minutes...", "active")
        try:
            result = await asyncio.to_thread(
                create_local_template_server,
                self.selected_template_id,
                server_name,
                Path(project_directory_text).expanduser(),
                template_option,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            error_message.update(f"Error: {exc}")
            self._set_message("Server setup failed. Check the error above.", "error")
            return
        finally:
            self.setup_in_progress = False
            self._set_setup_form_disabled(".local-setup-input", form_buttons, False)

        self._connect_and_show_dashboard(result.connection)
        next_step = f" {result.next_step}" if result.next_step else ""
        self._set_message(f"Created {result.server_name} in {result.project_dir}.{next_step}", "active")

    @work(group="local-setup")
    async def _register_custom_server(self) -> None:
        server_name = self.query_one("#custom-name", Input).value.strip()
        project_directory_text = self.query_one("#custom-directory", Input).value.strip()
        start_command = self.query_one("#custom-command", Input).value.strip()
        description = self.query_one("#custom-description", Input).value.strip()
        error_message = self.query_one("#custom-setup-error", Static)
        if not server_name or not project_directory_text or not start_command:
            error_message.update("Error: server name, folder, and start command are required.")
            self._set_message("The custom server details are incomplete.", "error")
            return
        if self.setup_in_progress:
            return
        self.setup_in_progress = True

        form_buttons = ("#close-custom-setup", "#create-custom-server")
        self._set_setup_form_disabled(".custom-setup-input", form_buttons, True)
        error_message.update("")
        self._set_message("Registering the server and starting the local Homebru agent...", "active")
        try:
            result = await asyncio.to_thread(
                create_local_custom_server,
                server_name,
                Path(project_directory_text).expanduser(),
                start_command,
                description,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            error_message.update(f"Error: {exc}")
            self._set_message("Server registration failed. Check the error above.", "error")
            return
        finally:
            self.setup_in_progress = False
            self._set_setup_form_disabled(".custom-setup-input", form_buttons, False)

        self._connect_and_show_dashboard(result.connection)
        self._set_message(f"Registered {result.server_name} in {result.project_dir}. {result.next_step}", "active")

    def _connect_using_form(self) -> None:
        entered_token = self.query_one("#token", Input).value
        token = entered_token or (self.config.token if self.config else "")
        try:
            config = ServerConfig(
                host=self.query_one("#host", Input).value,
                port=int(self.query_one("#port", Input).value or "8420"),
                token=token,
                scheme=self.query_one("#scheme", Input).value or "http",
                refresh_interval=self.config.refresh_interval if self.config else 2.0,
                request_timeout=self.config.request_timeout if self.config else 5.0,
            )
        except (ConfigError, ValueError) as exc:
            self.query_one("#connection-error", Static).update(f"Error: {exc}")
            self._set_message("The connection details are invalid.", "error")
            return
        self.query_one("#connection-error", Static).update("")
        self._connect_and_show_dashboard(config)

    @work(exclusive=True, group="open-dashboard")
    async def _open_saved_server(self) -> None:
        config = self.config
        if not config:
            self._set_message("No saved server is available.", "error")
            return
        button = self.query_one("#open-dashboard", Button)
        button.disabled = True
        is_local_server = config.host.lower() in {"127.0.0.1", "localhost"}
        self._set_message(
            "Starting the local agent..." if is_local_server else f"Opening {config.host}...",
            "active",
        )
        try:
            await asyncio.to_thread(ensure_local_agent, config)
        except (OSError, RuntimeError, ValueError) as exc:
            self._set_connection("Agent unavailable", "error")
            self._set_message(f"Could not start the saved server: {exc}", "error")
            return
        finally:
            button.disabled = False
        self._connect_and_show_dashboard(config)

    def _connect_and_show_dashboard(self, config: ServerConfig) -> None:
        self._replace_agent_client(config)
        self._save_connection_config(config)
        self._start_refresh_timer(config)
        self._hide_navigation_panels()
        self.query_one("#content-scroll", VerticalScroll).remove_class("hidden")
        self.query_one("#command", Input).focus()
        self._set_connection(f"Connecting to {config.host}...")
        self._set_message(f"Connecting to {config.host}...", "active")
        self.refresh_data()

    def _replace_agent_client(self, config: ServerConfig) -> None:
        old_client = self.client
        self.config = config
        self.client = AgentClient(config)
        self.dashboard_open = True
        if old_client:
            asyncio.create_task(old_client.close())

    def _save_connection_config(self, config: ServerConfig) -> None:
        if self.save_connection:
            try:
                save_config(config, self.config_path)
            except OSError as exc:
                self._set_message(f"Could not save the connection: {exc}", "error")

    def _start_refresh_timer(self, config: ServerConfig) -> None:
        if self.refresh_timer:
            self.refresh_timer.stop()
        self.refresh_timer = self.set_interval(config.refresh_interval, self.refresh_data)

    def _update_status_widget(self, selector: str, message: str, state: str) -> None:
        try:
            widget = self.query_one(selector, Static)
        except NoMatches:
            return
        widget.set_classes(state)
        widget.update(message)

    def _set_message(self, message: str, state: str = "") -> None:
        self._update_status_widget("#message-line", message, state)

    def _set_connection(self, message: str, state: str = "") -> None:
        self._update_status_widget("#connection-state", message, state)

    @work(group="refresh")
    async def refresh_data(self) -> None:
        client = self.client
        config = self.config
        if not client or not config or not self.dashboard_open or self.refresh_in_progress:
            return
        self.refresh_in_progress = True
        if not self.service_names:
            self._set_connection(f"Connecting to {config.host}...")
        try:
            stats, services = await asyncio.wait_for(
                asyncio.gather(client.get_stats(), client.get_services()),
                timeout=config.request_timeout + 0.5,
            )
        except asyncio.TimeoutError:
            if self.client is client and self.dashboard_open:
                self._set_connection("Connection timed out", "error")
                self._set_message(
                    "The agent took too long to respond. Check it is running, then press Refresh.",
                    "error",
                )
            return
        except AgentError as exc:
            if self.client is client and self.dashboard_open:
                self._set_connection("Connection failed", "error")
                self._set_message(f"Connection error: {exc}. Check the agent, then press Refresh.", "error")
            return
        finally:
            self.refresh_in_progress = False
        if self.client is client and self.dashboard_open:
            self._render_system_stats(stats)
            self._render_services(services)
            self._set_connection(f"Connected to {config.host}", "connected")
            self._set_message("Ready")

    def _render_system_stats(self, stats: dict[str, Any]) -> None:
        self._render_metric_cards(stats)
        self.query_one("#hardware-details", Static).update("\n".join(_format_hardware_lines(stats)))

    def _render_metric_cards(self, stats: dict[str, Any]) -> None:
        cpu = stats.get("cpu") or {}
        memory = stats.get("memory") or {}
        cores = cpu.get("core_count", "—")
        self.query_one("#cpu-card", MetricCard).set_value(cpu.get("percent"), f"{cores} logical cores")
        self.query_one("#memory-card", MetricCard).set_value(
            memory.get("percent"), f"{format_bytes(memory.get('used'))} of {format_bytes(memory.get('total'))}"
        )
        uptime = self.query_one("#uptime-card", MetricCard)
        uptime.query_one(".metric-value", Static).update(f"[b]{format_uptime(stats.get('uptime_seconds'))}[/]")
        uptime.query_one(".metric-detail", Static).update("since last boot")

    def _render_services(self, services: list[dict[str, Any]]) -> None:
        table = self.query_one("#service-table", DataTable)
        cursor = table.cursor_row
        table.clear()
        self.service_names = []
        for service in services:
            name = str(service.get("name", "unknown"))
            state = str(service.get("active_state", "unknown"))
            substate = str(service.get("sub_state", "unknown"))
            self.service_names.append(name)
            table.add_row(
                _service_status_label(state),
                name,
                f"{state} / {substate}",
                str(service.get("enabled", "unknown")),
                str(service.get("description", "")),
                key=name,
            )
        if self.service_names:
            table.move_cursor(row=min(cursor, len(self.service_names) - 1))

    def _selected_service(self) -> str | None:
        table = self.query_one("#service-table", DataTable)
        if not self.service_names or table.cursor_row >= len(self.service_names):
            self._set_message("Select a service first.", "error")
            return None
        return self.service_names[table.cursor_row]

    @work(exclusive=True, group="service-action")
    async def _control_service(self, action: ServiceAction, service_name: str | None = None) -> None:
        name = service_name or self._selected_service()
        if not name or not self.client:
            return
        self._set_message(f"Running {action} on {name}...", "active")
        try:
            await self.client.control_service(name, action)
        except AgentError as exc:
            self._set_message(f"Service error: {exc}", "error")
            return
        self._set_message(f"{action.title()} completed for {name}.", "active")
        self.refresh_data()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        template_id = TEMPLATE_BUTTONS.get(button_id)
        if template_id:
            self._show_template_form(template_id)
        elif button_id == "open-dashboard" and self.config:
            self._open_saved_server()
        elif button_id == "setup-templates":
            self._show_template_picker()
        elif button_id == "connect-existing":
            self._show_connection()
        elif button_id == "setup-custom":
            self._show_custom_form()
        elif button_id in {"close-template-picker", "close-custom-setup", "close-connection"}:
            self._show_home()
        elif button_id == "close-local-setup":
            self._close_template_form()
        elif button_id == "create-local-server":
            self._create_server_from_template()
        elif button_id == "create-custom-server":
            self._register_custom_server()
        elif button_id == "connect":
            self._connect_using_form()
        elif button_id == "refresh":
            self._set_message("Refreshing...", "active")
            self.refresh_data()
        elif button_id == "home":
            self._show_home()
        elif button_id in {"start", "stop", "restart"}:
            self._control_service(button_id)  # type: ignore[arg-type]

    @on(Input.Submitted, "#connection-panel .connection-input")
    def on_connection_submitted(self) -> None:
        self._connect_using_form()

    @on(Input.Submitted, "#template-option")
    def on_template_form_submitted(self) -> None:
        self._create_server_from_template()

    @on(Input.Submitted, "#custom-command")
    def on_custom_form_submitted(self) -> None:
        self._register_custom_server()

    @on(Input.Changed, "#command")
    def on_command_changed(self, event: Input.Changed) -> None:
        self._update_command_suggestions(event.value)

    def on_key(self, event: events.Key) -> None:
        command_input = self.query_one("#command", Input)
        if not command_input.has_focus or not self.command_suggestions:
            return
        if event.key == "up":
            event.stop()
            event.prevent_default()
            self.selected_suggestion_index = (self.selected_suggestion_index - 1) % len(self.command_suggestions)
            self._render_command_suggestions()
        elif event.key == "down":
            event.stop()
            event.prevent_default()
            self.selected_suggestion_index = (self.selected_suggestion_index + 1) % len(self.command_suggestions)
            self._render_command_suggestions()
        elif event.key == "tab":
            event.stop()
            event.prevent_default()
            self._complete_selected_suggestion()

    def _update_command_suggestions(self, input_value: str) -> None:
        self.command_suggestions = _autocomplete_options(input_value, self.service_names)
        self.selected_suggestion_index = 0
        self._render_command_suggestions()

    def _render_command_suggestions(self) -> None:
        suggestion_list = self.query_one("#command-suggestions", Static)
        if not self.command_suggestions:
            suggestion_list.update("")
            suggestion_list.add_class("hidden")
            return

        last_window_start = max(len(self.command_suggestions) - MAX_VISIBLE_AUTOCOMPLETE_OPTIONS, 0)
        window_start = min(
            max(self.selected_suggestion_index - MAX_VISIBLE_AUTOCOMPLETE_OPTIONS + 1, 0),
            last_window_start,
        )
        visible_suggestions = self.command_suggestions[
            window_start : window_start + MAX_VISIBLE_AUTOCOMPLETE_OPTIONS
        ]

        rendered_suggestions = Text()
        for visible_index, option in enumerate(visible_suggestions):
            index = window_start + visible_index
            selected = index == self.selected_suggestion_index
            option_style = "bold #E5E5E5" if selected else "#808080"
            rendered_suggestions.append("> " if selected else "  ", style=option_style)
            rendered_suggestions.append(option.label, style=option_style)
            rendered_suggestions.append(f"  {option.description}", style="#808080")
            if visible_index < len(visible_suggestions) - 1:
                rendered_suggestions.append("\n")
        suggestion_list.update(rendered_suggestions)
        suggestion_list.remove_class("hidden")

    def _complete_selected_suggestion(self) -> None:
        if not self.command_suggestions:
            return
        completion = self.command_suggestions[self.selected_suggestion_index].value
        command_input = self.query_one("#command", Input)
        command_input.value = completion
        command_input.cursor_position = len(completion)
        command_input.focus()
        self._update_command_suggestions(completion)

    def _clear_command_suggestions(self) -> None:
        self.command_suggestions = []
        self.selected_suggestion_index = 0
        self._render_command_suggestions()

    @on(Input.Submitted, "#command")
    def on_command_submitted(self, event: Input.Submitted) -> None:
        raw_command = event.value.strip()
        if raw_command and self.command_suggestions:
            selected_value = self.command_suggestions[self.selected_suggestion_index].value.strip()
            if raw_command.casefold() != selected_value.casefold():
                self._complete_selected_suggestion()
                return
        self._clear_command_suggestions()
        event.input.value = ""
        if not raw_command:
            return
        command, _, argument = raw_command.removeprefix("/").partition(" ")
        self._execute_command(command.lower(), argument.strip())

    def _execute_command(self, command: str, argument: str) -> None:
        if command in {"start", "stop", "restart"}:
            self._control_service(command, argument or None)  # type: ignore[arg-type]
        elif command in {"refresh", "r"}:
            self.refresh_data()
        elif command in {"connect", "connection"}:
            self._show_connection()
        elif command in {"setup", "new"}:
            self._show_template_picker()
        elif command in {"custom", "scratch"}:
            self._show_custom_form()
        elif command in {"home", "menu"}:
            self._show_home()
        elif command in {"quit", "exit", "q"}:
            self.exit()
        elif command == "help":
            self._set_message(HELP_TEXT, "active")
        else:
            self._set_message(f"Unknown command: {command}. Type /help for available commands.", "error")

    def action_refresh(self) -> None:
        self.refresh_data()

    def action_focus_command(self) -> None:
        self.query_one("#command", Input).focus()
