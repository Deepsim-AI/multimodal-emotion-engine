"""Minimal HTTPS static file server for the MEE remote demo client.

Replaces `python3 -m http.server 8082` with an HTTPS variant so browsers
accept camera/mic permissions (secure context required).

Usage:
    python3 https_server.py [--port PORT] [--certfile PATH] [--keyfile PATH]
"""
import argparse
import ssl
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class Handler(SimpleHTTPRequestHandler):
    """Serve files with Server header stripped to reduce fingerprinting."""
    server_version = "MEE-Demo"
    sys_version = ""


def main() -> None:
    parser = argparse.ArgumentParser(description="MEE Demo HTTPS static server")
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--certfile", default="/tmp/mee-cert.pem")
    parser.add_argument("--keyfile", default="/tmp/mee-key.pem")
    parser.add_argument("--directory", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()

    srv = HTTPServer(("0.0.0.0", args.port), Handler)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(args.certfile, args.keyfile)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)

    print(f"==> HTTPS static page on https://0.0.0.0:{args.port}/")
    print(f"    (accept browser cert warning — self-signed)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.server_close()


if __name__ == "__main__":
    main()
