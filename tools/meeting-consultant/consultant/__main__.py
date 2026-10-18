"""Command line: run the server, or send the bot into a meeting via a running server.

    python -m consultant serve
    python -m consultant join https://meet.google.com/abc-defg-hij --topic "MVP scoping"
    python -m consultant ask "What are the main UK rules for open banking apps?"
"""
import argparse
import os
import sys

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(prog="consultant")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="run the web server")
    serve.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    join = sub.add_parser("join", help="send the bot into a meeting")
    join.add_argument("meeting_url")
    join.add_argument("--topic", default="")
    join.add_argument("--context", default="")
    join.add_argument("--mode", choices=["chat", "voice"], default=None)
    ask = sub.add_parser("ask", help="ask the standalone assistant")
    ask.add_argument("text", nargs="+")
    args = parser.parse_args()

    if args.cmd == "serve":
        import uvicorn
        uvicorn.run("consultant.app:create_app", factory=True, host="0.0.0.0", port=args.port)
        return

    server = os.environ.get("SERVER_URL") or os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000")
    headers = {"x-admin-token": os.environ.get("ADMIN_TOKEN", "")}
    if args.cmd == "join":
        r = httpx.post(f"{server.rstrip('/')}/api/join", headers=headers, timeout=60,
                       json={"meeting_url": args.meeting_url, "topic": args.topic, "context": args.context,
                             "mode": args.mode})
    else:
        r = httpx.post(f"{server.rstrip('/')}/api/assistant", headers=headers, timeout=300,
                       json={"text": " ".join(args.text)})
    if r.status_code >= 400:
        sys.exit(f"Error {r.status_code}: {r.text}")
    data = r.json()
    print(data.get("reply") or f"Bot sent. Live page: {server.rstrip('/')}/meetings/{data['id']}")


if __name__ == "__main__":
    main()
