"""Retorna a primeira porta TCP livre em 127.0.0.1 a partir de `start`."""

from __future__ import annotations

import socket
import sys


def find_free_port(start: int = 8501, limit: int = 50) -> int:
    for port in range(start, start + limit):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"Nenhuma porta livre entre {start} e {start + limit - 1}.")


if __name__ == "__main__":
    port_start = int(sys.argv[1]) if len(sys.argv) > 1 else 8501
    port_limit = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    print(find_free_port(port_start, port_limit))
