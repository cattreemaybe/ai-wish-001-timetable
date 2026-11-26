"""DSH sidecar entry point.

Binds an OS-assigned loopback port, announces it on stdout, then serves the
FastAPI app on that socket.  The DSH host plugin captures the port and proxies
`/plugins/aiwish/*` to it.  No Python installation or PATH setup is required by
the user; the plugin ships its own runtime.
"""
from __future__ import annotations

import os
import socket

import uvicorn

from .main import app


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    port = sock.getsockname()[1]
    print(f"AIWISH_PORT={port}", flush=True)
    config = uvicorn.Config(
        app,
        log_level=os.environ.get("AIWISH_LOG_LEVEL", "warning"),
        access_log=False,
        lifespan="off",
    )
    server = uvicorn.Server(config)
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
