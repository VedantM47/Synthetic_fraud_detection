"""Run the web app: ``python -m backend`` (then open http://127.0.0.1:8000)."""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the fraud ring detection web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Restart on code changes (development).")
    args = parser.parse_args()
    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
