#!/usr/bin/env python3
"""Static server for KINETIC.

The game needs a webcam, and browsers only hand one over on a secure origin.
A file:// path is not one of those, so open the game through here instead:

    python3 serve.py        ->  http://localhost:1268/

http://localhost counts as secure, which is all getUserMedia is asking for.
"""

import argparse
import http.server
import os
import socketserver
import webbrowser

PORT = 1268
ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def end_headers(self):
        # the page is edited constantly; a cached copy is never what you want
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if "favicon" not in (args[0] if args else ""):
            super().log_message(fmt, *args)


class Server(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-p", "--port", type=int, default=PORT)
    ap.add_argument("-n", "--no-open", action="store_true",
                    help="do not open a browser")
    args = ap.parse_args()

    url = "http://localhost:%d/" % args.port
    with Server(("127.0.0.1", args.port), Handler) as httpd:
        print("KINETIC serving %s" % ROOT)
        print("  %s" % url)
        print("  ctrl-c to stop")
        if not args.no_open:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
