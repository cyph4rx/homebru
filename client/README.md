# Home Server Manager — Client

Electron + React (Vite) desktop app. Connects to a `homeserver-agent`
running on the Linux server (see `../agent`) to show live CPU/GPU/RAM/disk
stats and control systemd services, in a retro terminal theme.

## Develop

```bash
npm install
npm run electron:dev
```

This starts the Vite dev server and Electron together with hot reload for
the renderer.

## Build a standalone .exe

```bash
npm run dist
```

Output goes to `release/` (via `electron-builder`, NSIS installer target).

## First run

On first launch you'll see a CONNECT TO SERVER screen — enter the agent's
LAN IP, port (default `8420`), and the token printed when the agent first
started (see `../agent/README.md`). The connection is saved locally via
`electron-store` so you won't need to re-enter it.
