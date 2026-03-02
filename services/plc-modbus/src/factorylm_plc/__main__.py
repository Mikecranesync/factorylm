"""Entry point: python -m factorylm_plc [--mock] [--port PORT]"""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="FactoryLM PLC Backend")
    parser.add_argument("--mock", action="store_true", help="Run with simulated PLC (no hardware)")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port (default: 8000)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    args = parser.parse_args()

    if args.mock:
        os.environ["FACTORYLM_MOCK_MODE"] = "true"

    # Must import uvicorn after setting env vars
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
