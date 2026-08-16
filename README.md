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
- live view of your CPU, memory, uptime, disk, GPU, systemd, and Windows Services
- templates for Discord, Minecraft Java, Python, and Node.js servers
- A guided path for setting up your own server from scratch
- Quick commands like `/start`, `/stop`, `/restart`, `/setup`, `/custom`, and `/connect`
- Your connection settings are saved per user.
- Better looking **errors** for **timeouts**, **auth problems**, and **bad responses**

## Quick start

### 1. Install Homebru

On the computer you'll use to manage the server:

```powershell
cd D:\path\to\homebru
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
homebru
```

On Linux or macOS, use `source .venv/bin/activate` instead.

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
add it to the generated `.env` file before starting the bot. Check
[`agent/README.txt`](agent/README.txt) for the Discord Developer Portal steps.

Setting up a **remote computer?** Copy the `agent/` folder over to it and follow
the short headless setup in [`agent/README.txt`](agent/README.txt), then pick
**Connect to an existing server** back in Homebru. Keep the agent on a
trusted private network — don't expose port `8420` directly to the public
internet.

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

## Terminal controls

| Action | How |
|---|---|
| Browse command suggestions | Type `/` or start typing a slash command |
| Choose and complete a suggestion | Use `Up` / `Down`, then press `Tab` |
| Complete a service name | Type `/start `, `/stop `, or `/restart ` and begin typing its name |
| Select a service | Arrow keys or mouse, then use the action buttons |
| Focus the command input | `Esc` |
| Start / stop / restart the selected service | `/start`, `/stop`, `/restart` |
| Target a service directly | Add its name, e.g. `/restart docker` |
| Browse server templates | `/setup` |
| Register a custom server | `/custom` |
| Change servers | `/connect` |
| Return to the home screen | Home button or `/home` |
| Refresh now | `/refresh` |
| Show help | `/help` |
| Quit | `Ctrl+C` or `/quit` |
