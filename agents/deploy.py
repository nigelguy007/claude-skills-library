#!/usr/bin/env python3
"""
Deploy Claude Platform agents using the API directly.
Alternative to 'ant apply' while the ant CLI is unavailable.

Usage:
    python3 deploy.py agents/disruptive-ai-storyteller/
    python3 deploy.py --list
    python3 deploy.py --delete <agent_id>
"""

import os
import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Any, Optional
import frontmatter

CLAUDE_PLATFORM_API = "https://api.claude.com/v1"


def get_api_key() -> str:
    """Get Claude Platform API key from environment."""
    key = os.getenv("CLAUDE_API_KEY")
    if not key:
        raise ValueError(
            "CLAUDE_API_KEY environment variable not set. "
            "Get your API key from https://console.anthropic.com"
        )
    return key


def parse_agent_file(agent_path: Path) -> tuple[dict, str]:
    """Parse agent .md file into config dict and system prompt."""
    with open(agent_path, "r") as f:
        post = frontmatter.load(f)

    config = post.metadata
    system_prompt = post.content.strip()

    return config, system_prompt


def load_lock_file(agent_dir: Path) -> dict:
    """Load claude-lock.json to get agent ID if it exists."""
    lock_file = agent_dir / "claude-lock.json"
    if lock_file.exists():
        with open(lock_file) as f:
            return json.load(f)
    return {}


def save_lock_file(agent_dir: Path, lock_data: dict) -> None:
    """Save agent ID to claude-lock.json for future updates."""
    lock_file = agent_dir / "claude-lock.json"
    with open(lock_file, "w") as f:
        json.dump(lock_data, f, indent=2)


def create_agent(api_key: str, config: dict, system_prompt: str) -> dict:
    """Create a new agent on Claude Platform."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {**config, "instructions": system_prompt}

    response = requests.post(
        f"{CLAUDE_PLATFORM_API}/agents",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def update_agent(api_key: str, agent_id: str, config: dict, system_prompt: str) -> dict:
    """Update an existing agent on Claude Platform."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {**config, "instructions": system_prompt}

    response = requests.patch(
        f"{CLAUDE_PLATFORM_API}/agents/{agent_id}",
        json=payload,
        headers=headers,
    )
    response.raise_for_status()
    return response.json()


def deploy_agent(agent_dir: str, dry_run: bool = False) -> None:
    """Deploy or update an agent from a directory."""
    agent_dir = Path(agent_dir)

    if not agent_dir.is_dir():
        raise ValueError(f"Agent directory not found: {agent_dir}")

    # Find the agent .md file
    md_files = list(agent_dir.glob("*.md"))
    md_files = [f for f in md_files if f.name != "README.md"]

    if not md_files:
        raise ValueError(f"No agent definition found in {agent_dir}")

    agent_file = md_files[0]
    config, system_prompt = parse_agent_file(agent_file)
    lock_data = load_lock_file(agent_dir)

    print(f"📋 Agent: {config.get('name', 'Unknown')}")
    print(f"📝 File: {agent_file.name}")

    if dry_run:
        print("\n🔍 DRY RUN - Config that would be sent:")
        print(json.dumps({**config, "instructions": system_prompt[:100] + "..."}, indent=2))
        return

    api_key = get_api_key()

    if "agents" in lock_data and lock_data["agents"].get(str(agent_file)):
        # Update existing agent
        agent_id = lock_data["agents"][str(agent_file)]["id"]
        print(f"🔄 Updating agent {agent_id}...")
        result = update_agent(api_key, agent_id, config, system_prompt)
        print(f"✅ Updated: {agent_id}")
    else:
        # Create new agent
        print(f"🚀 Creating new agent...")
        result = create_agent(api_key, config, system_prompt)
        agent_id = result["id"]

        if "agents" not in lock_data:
            lock_data["agents"] = {}
        lock_data["agents"][str(agent_file)] = {"id": agent_id}
        save_lock_file(agent_dir, lock_data)

        print(f"✅ Created: {agent_id}")

    print(f"🔗 View: https://console.anthropic.com/agents/{result['id']}")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy Claude Platform agents without ant CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 deploy.py agents/disruptive-ai-storyteller/
  python3 deploy.py agents/disruptive-ai-storyteller/ --dry-run
  python3 deploy.py agents/*/
        """,
    )
    parser.add_argument("path", nargs="?", help="Agent directory to deploy")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without deploying",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List deployed agents from lock files",
    )

    args = parser.parse_args()

    if args.list:
        # List agents
        agents_dir = Path("agents")
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir():
                lock_file = agent_dir / "claude-lock.json"
                if lock_file.exists():
                    with open(lock_file) as f:
                        lock = json.load(f)
                        for file, info in lock.get("agents", {}).items():
                            print(f"{agent_dir.name}: {info['id']}")
        return

    if not args.path:
        parser.print_help()
        sys.exit(1)

    try:
        deploy_agent(args.path, dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
