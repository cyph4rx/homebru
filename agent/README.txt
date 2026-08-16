this is the Homebru agent.

It runs on the computer you want to manage. It reports hardware stats and
starts, stops, or restarts apps registered with Homebru. Works the same way
on Windows and Linux.

SETUP FROM HOMEBRU

If Homebru and the server are on the same computer, you don't need to touch
this folder by hand at all. Just run `homebru`, pick anything from the
server templates or create from scratch, and it sets up the local agent and
connects to it for you.

You'll need Python 3.10 or newer either way.

HEADLESS OR EXTERNAL-COMPUTER SETUP

For a different computer, copy this whole `agent` folder over to it, open a
terminal there, and run:

  python setup_agent.py

That creates the agent's virtual environment, installs what it needs, and
generates its config and token. (It also asks a couple of quick questions
to set up a starter app alongside it, safe to just accept the defaults or
skip with `--skip-install` if you'd rather do that part later.)

Start the agent with:

  python run_agent.py

Leave that terminal running. Then, on your main computer, open Homebru,
choose Connect to an existing server, and enter:

- Host: the server computer's LAN IP, or 127.0.0.1 if it's the same PC.
- Port: 8420.
- Token: the one setup printed for you.

GETTING THE TOKEN AGAIN

If you lose the token or just need to check it later:

  python run_agent.py --show-token

And to see where the config file itself lives:

  python run_agent.py --show-config

It's stored at `data/config.json`. Treat the token like a password - don't
share or commit it.

USEFUL COMMANDS

  python run_agent.py                 Start the agent
  python run_agent.py --show-token    Show the Homebru token again
  python run_agent.py --show-config   Show the configuration path
  python setup_agent.py --help        Show non-interactive setup options

EXISTING OPERATING-SYSTEM SERVICES

Homebru can also manage existing systemd or Windows services, not just apps
it set up itself. Add their exact service names to `allowed_services` in
`data/config.json`, then restart the agent. `config.example.json` in this
folder shows the shape it expects.

Service control may need Administrator on Windows or root on Linux. Managed
apps run as the same user running the agent.

RUNNING THE AGENT AS A SYSTEMD SERVICE (LINUX)

If you'd rather the agent start on boot instead of running it in a terminal,
use the included `homeserver-agent.service` unit:

1. Copy this whole `agent` folder to the server, e.g. `/opt/homebrew-agent`.
2. Run `python setup_agent.py` there once to create the `.venv` and config.
3. Edit `WorkingDirectory` and `ExecStart` in `homeserver-agent.service` if
   you copied it somewhere other than `/opt/homebrew-agent`.
4. Install and start it:

  sudo cp homeserver-agent.service /etc/systemd/system/
  sudo systemctl enable --now homeserver-agent

Check it's running with `systemctl status homeserver-agent`, and logs with
`journalctl -u homeserver-agent -f`.

NETWORK SAFETY

The agent uses plain HTTP by default. Keep it on a trusted private network
and don't port foward 8420 from your router. Use an HTTPS reverse proxy if
the agent needs to be reached over an untrusted network.
