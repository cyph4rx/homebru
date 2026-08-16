this is the Homebru agent.

It runs on the computer you want to manage. It reports hardware stats and
starts, stops, or restarts apps registered with Homebru. Works the same way
on Windows and Linux.

SETUP FROM HOMEBRU

If Homebru and the server are on the same computer, just run `homebru` and
pick Server templates or Create from scratch. It'll ask you what it needs,
do the setup, and connect to the local agent for you.

Templates you can pick from:

- Discord bot: a discord.py starter with /ping and /hello already wired up.
- Minecraft Java: sets up the config and startup files; you bring your own
  official server.jar and accept the EULA yourself.
- Python web server: a standard-library static web server, nothing to install.
- Node.js web server: a dependency-free HTTP starter (Node.js has to already
  be installed).

Create from scratch just registers a folder you already have and the exact
command to start it, like `python server.py`, `node server.js`, or
`java -jar server.jar nogui`.

You'll need Python 3.10 or newer.

HEADLESS OR EXTERNAL-COMPUTER SETUP

Open a terminal in this `agent` folder and run:

  python setup_agent.py

It'll ask you for:

1. A name for your Discord bot.
2. The folder its files should go in.
3. The Discord bot token (fine to leave blank and add later).

Then it creates the bot, installs the Python packages it needs, registers it
with Homebru, and prints your Homebru agent token.

Start the agent with:

  python run_agent.py

Leave that terminal running. Then, on your main computer, open Homebru,
choose Connect to an existing server, and enter:

- Host: the server computer's LAN IP, or 127.0.0.1 if it's the same PC.
- Port: 8420.
- Token: the one setup printed for you.

The Discord bot will show up in the Services list, ready to start, stop, or
restart from Homebru.

CREATING THE DISCORD BOT TOKEN

1. Open https://discord.com/developers/applications.
2. Click New Application, give it a name, then open its Bot page.
3. Create or reset the token and paste it into the Homebru setup prompt.
4. Under OAuth2 > URL Generator, check `bot` and `applications.commands`,
   then use the generated URL to invite the bot to your server.

The template uses slash commands, so it doesn't need the privileged Message
Content intent. It comes with /ping and /hello.

Never share or commit the Discord token. Setup saves it in the bot's `.env`
file, which the generated .gitignore already excludes.

FILES CREATED BY SETUP

  agent/
    .venv/                       Agent Python environment
    data/config.json             Agent token and registered apps
    servers/discord-bot/
      .env                       Discord token
      .venv/                     Bot Python environment
      bot.py                     Bot source code
      requirements.txt           Bot dependency
      homebrew.log               Bot output after it starts

The folder and bot name will match whatever you answer in the wizard.

USEFUL COMMANDS

  python run_agent.py                 Start the agent
  python run_agent.py --show-token    Show the Homebru token again
  python run_agent.py --show-config   Show the configuration path
  python setup_agent.py --help        Show non-interactive setup options

Use `python setup_agent.py --skip-install` if you just want the files and
would rather install dependencies yourself. It'll print the commands you need.

EXISTING OPERATING-SYSTEM SERVICES

Homebru can still manage existing systemd or Windows services too. Add their
exact service names to `allowed_services` in `data/config.json`, then restart
the agent. This is optional and not needed for the Discord bot template.

Service control may need Administrator on Windows or root on Linux. Managed
apps like the Discord bot run as the same user running the agent.

NETWORK SAFETY

The agent uses plain HTTP by default. Keep it on a trusted private network
and don't forward port 8420 from your router. Use an HTTPS reverse proxy if
the agent needs to be reached over an untrusted network.
