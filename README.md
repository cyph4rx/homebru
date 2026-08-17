```
 ██╗  ██╗ ██████╗ ███╗   ███╗███████╗██████╗ ██████╗ ██╗   ██╗
 ██║  ██║██╔═══██╗████╗ ████║██╔════╝██╔══██╗██╔══██╗██║   ██║
 ███████║██║   ██║██╔████╔██║█████╗  ██████╔╝██████╔╝██║   ██║
 ██╔══██║██║   ██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██╗██║   ██║
 ██║  ██║╚██████╔╝██║ ╚═╝ ██║███████╗██████╔╝██║  ██║╚██████╔╝
 ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝
```

A terminal app that lets you host servers on your PC, with an easy-to-use
interface to get you started even if you've never ran a server.

## Features

- a native, cool-looking **terminal** GUI
- self-contained Windows and Linux builds that do not require Python
- live view of your CPU, memory, uptime, disk, GPU, systemd, and Windows Services
- live logs and console input for Homebru-managed servers
- templates for Discord, Minecraft Java, Python, and Node.js servers
- A guided path for setting up your own server from scratch
- Quick commands like `/start`, `/stop`, `/restart`, `/setup`, `/custom`, and `/connect`
- Your connection settings are saved per user.
- Better looking **errors** for **timeouts**, **auth problems**, and **bad responses**

## Quick start

### 1. Install Homebru

#### Standalone release

The standalone build is the simplest option. Download the Windows or Linux
artifact produced by the **Standalone builds** workflow and run `homebru.exe`
on Windows or `homebru` on Linux. Python and Homebru's Python packages are
included inside the executable.

Linux users need to make the downloaded file executable once:

```bash
chmod +x homebru
./homebru
```

#### Install from source

The source installer requires **Python 3.10** or newer.

On Windows, run the shared Python installer by its full path from PowerShell:

```powershell
python "D:\path\to\homebru\install.py"
```

On Linux or macOS, use the small shell launcher:

```bash
sh /path/to/homebru/install.sh
```

Close and reopen your terminal after installation. You can then launch
Homebru from any folder:

```powershell
homebru
```

To uninstall the command,
run `python "D:\path\to\homebru\install.py" --uninstall` on Windows or
`sh /path/to/homebru/install.sh --uninstall` on Linux and macOS.

### 2. Choose your setup inside Homebru

Run `homebru` and you'll land on a home screen with three options:

- **Server templates** — a list of ready-to-go starters: Discord bot,
  Minecraft Java, Python web server, and Node.js web server.
- **Create from scratch** — point Homebru at a folder and a start command
  for a server you already have, or want to build yourself. The form walks
  you through it with instructions and examples.
- **Connect to an existing server** — hook up to a different Windows or
  Linux machine by entering its IP, port, and agent token.

Once youve saved a connection, an **Open saved server** button shows up there too.
Homebru only connects once you actually choose it. You can jump back here
anytime with the **Home** button or `/home`.

Local templates handle the install/setup for you, start the local Homebru
agent, and connect the dashboard automatically. The Minecraft template
won't download the proprietary server files or accept the EULA for you,
its generated `README.txt` walks you through adding `server.jar` and
finishing setup yourself. The Node.js template needs Node.js already
installed.

The Discord token is optional while setting up. leave it blank and just
add it to the generated `.env` file before starting the bot. Its generated
`READ.txt` covers the Discord Developer Portal steps.

Setting up a **remote computer?** Copy the `agent/` folder over to it and follow
the short headless setup in [`agent/README.txt`](agent/README.txt), then pick
**Connect to an existing server** back in Homebru. Keep the agent on a
trusted private network — don't expose port `8420` directly to the public
internet.

The standalone executable can also run the agent without copying the source
folder. On the computer you want to manage, run:

```powershell
homebru.exe --agent
```

Use `homebru.exe --show-agent-token` on that computer to retrieve its token.

Connections get saved to `%APPDATA%\homebrew\config.json` on Windows, or
`~/.config/homebrew/config.json` on Linux.

## Getting the agent token

Run this from inside the copied `agent` directory after setup:

```powershell
python run_agent.py --show-token
```

The first time it runs, Homebru creates the token and prints it out. Use
the command above any time after that to look it up again. If you want to
see where the config file actually lives:

```powershell
python run_agent.py --show-config
```

It's stored at `agent/data/config.json` on both Windows and Linux. Treat
that token like a password.

You can also skip the menus entirely and connect straight from the command
line:

```powershell
homebru --host 192.168.1.50 --port 8420 --token YOUR_TOKEN --no-save
```

Run `homebru --help` to see everything else you can pass in.

## Live logs and server console

Select a Homebru-managed server in the dashboard and choose **Console**, or run
`/console SERVER_NAME`. The latest output refreshes once per second. Enter a
command in the console input and press Enter to send it to the running server.

Operating-system services do not expose an interactive console through
Homebru. If the Homebru agent was restarted while a managed server stayed
running, restart that server from Homebru once to reconnect its console input.
Its existing logs remain available.

## Terminal controls

| Action | How |
|---|---|
| Browse command suggestions | Type `/` or start typing a slash command |
| Choose and complete a suggestion | Use `Up` / `Down`, then press `Tab` |
| Complete a service name | Type `/start `, `/stop `, `/restart `, or `/console ` and begin typing its name |
| Select a service | Arrow keys or mouse, then use the action buttons |
| Focus the command input | `Esc` |
| Start / stop / restart the selected service | `/start`, `/stop`, `/restart` |
| Target a service directly | Add its name, e.g. `/restart docker` |
| Open live server logs and console | Console button or `/console SERVER_NAME` |
| Browse server templates | `/setup` |
| Register a custom server | `/custom` |
| Change servers | `/connect` |
| Return to the home screen | Home button or `/home` |
| Refresh now | `/refresh` |
| Show help | `/help` |
| Quit | `Ctrl+C` or `/quit` |

## Building standalone releases

Install the release tools and build on the target operating system:

```powershell
python -m pip install ".[release]"
python -m PyInstaller --clean --noconfirm homebru.spec
```

The result is `dist/homebru.exe` on Windows or `dist/homebru` on Linux. Builds
are operating-system-specific, so create the Windows build on Windows and the
Linux build on Linux. The workflow in
`.github/workflows/standalone-builds.yml` builds and smoke-tests both versions.
