from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="{{SERVER_NAME}} web server")
    parser.add_argument("--port", type=int, default={{PORT}})
    args = parser.parse_args()
    public_dir = Path(__file__).with_name("public")
    request_handler = partial(SimpleHTTPRequestHandler, directory=public_dir)
    http_server = ThreadingHTTPServer(("0.0.0.0", args.port), request_handler)
    print(f"Serving {public_dir} on http://0.0.0.0:{args.port}", flush=True)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        http_server.server_close()


if __name__ == "__main__":
    main()
