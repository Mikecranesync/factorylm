"""
MJPEG webcam server for the PLC laptop.

Captures from a USB webcam and serves an MJPEG stream on port 8081.
The VPS conveyor-relay proxies this stream to the public internet.

Usage:
    python webcam.py                 # Default device 0, port 8081
    python webcam.py --device 1      # Use device 1
    python webcam.py --port 9090     # Custom port
"""

import argparse
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock

import cv2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("webcam-mjpeg")

# Global frame buffer
_frame: bytes | None = None
_lock = Lock()


def capture_loop(device: int):
    """Continuously capture frames from the webcam."""
    global _frame
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        logger.error("Cannot open webcam device %d", device)
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    logger.info("Webcam device %d opened (%.0fx%.0f)",
                device, cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        with _lock:
            _frame = jpeg.tobytes()
        time.sleep(0.033)  # ~30 fps cap


class MJPEGHandler(BaseHTTPRequestHandler):
    """Serve MJPEG stream on /stream and a simple health check on /."""

    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                while True:
                    with _lock:
                        frame = _frame
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.033)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","service":"webcam-mjpeg"}')
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress per-request logs
        pass


def main():
    parser = argparse.ArgumentParser(description="MJPEG webcam server")
    parser.add_argument("--device", type=int, default=0, help="Webcam device index")
    parser.add_argument("--port", type=int, default=8081, help="HTTP port")
    args = parser.parse_args()

    # Start capture in background thread
    t = Thread(target=capture_loop, args=(args.device,), daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", args.port), MJPEGHandler)
    logger.info("MJPEG server on http://0.0.0.0:%d/stream", args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
