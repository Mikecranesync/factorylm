"""Cosmos Demo HMI Launcher

Opens the conveyor-relay HMI directly in the default browser.
If relay.py is running (port 8400), connects to live PLC.
Otherwise, use the "Run Demo Scenario" button for offline demo.
"""

import http.server
import os
import threading
import webbrowser

PORT = 8401
STATIC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "services", "conveyor-relay", "static"
)


def main():
    static = os.path.abspath(STATIC_DIR)
    if not os.path.isdir(static):
        print(f"Error: static dir not found at {static}")
        return

    os.chdir(static)
    handler = http.server.SimpleHTTPRequestHandler
    server = http.server.HTTPServer(("127.0.0.1", PORT), handler)

    print(f"Serving HMI from {static}")
    print(f"Open http://127.0.0.1:{PORT}/index.html")
    print("Press Ctrl+C to stop\n")

    # Open browser after short delay
    def open_browser():
        webbrowser.open(f"http://127.0.0.1:{PORT}/index.html")

    threading.Timer(0.5, open_browser).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
