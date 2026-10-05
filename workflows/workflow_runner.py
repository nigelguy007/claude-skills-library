#!/usr/bin/env python3
"""
Workflow executor for orchestrating Claude Platform agents.

Parses YAML workflow definitions and executes agent steps sequentially,
passing outputs from one step to the next.

Usage:
    python3 workflow_runner.py workflows/daily-linkedin-post.yaml
    python3 workflow_runner.py workflows/daily-linkedin-post.yaml --dry-run
"""

import os
import sys
import json
import yaml
import argparse
import requests
from pathlib import Path
from typing import Any, Dict, Optional, List
import re
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

CLAUDE_PLATFORM_API = os.getenv("CLAUDE_PLATFORM_API", "https://api.claude.com/v1")


class WorkflowExecutor:
    """Executes workflow steps sequentially with data passing between steps."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CLAUDE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "CLAUDE_API_KEY environment variable not set. "
                "Get your API key from https://console.anthropic.com"
            )
        self.step_outputs = {}
        self.workflow_data = {}

    def load_workflow(self, workflow_path: str) -> Dict[str, Any]:
        """Load workflow definition from YAML file."""
        with open(workflow_path, "r") as f:
            self.workflow_data = yaml.safe_load(f)
        return self.workflow_data

    def substitute_variables(self, value: Any) -> Any:
        """
        Replace template variables in value.
        Supports: {{ steps[n].output }}, {{ env.VAR_NAME }}, {{ workflow.key }}
        """
        if not isinstance(value, str):
            return value

        # Replace step outputs: {{ steps[0].output }}
        step_pattern = r'\{\{\s*steps\[(\d+)\]\.output\s*\}\}'
        for match in re.finditer(step_pattern, value):
            step_idx = int(match.group(1))
            if step_idx in self.step_outputs:
                output = self.step_outputs[step_idx]
                # If the entire string is just the template, return the actual value
                if value == match.group(0):
                    return output
                # Otherwise substitute as string
                value = value.replace(match.group(0), str(output))

        # Replace env vars: {{ env.VAR_NAME }}
        env_pattern = r'\{\{\s*env\.(\w+)\s*\}\}'
        for match in re.finditer(env_pattern, value):
            var_name = match.group(1)
            env_value = os.getenv(var_name, "")
            value = value.replace(match.group(0), env_value)

        # Replace workflow vars: {{ workflow.key }}
        workflow_pattern = r'\{\{\s*workflow\.(\w+)\s*\}\}'
        for match in re.finditer(workflow_pattern, value):
            key = match.group(1)
            workflow_value = self.workflow_data.get(key, "")
            value = value.replace(match.group(0), str(workflow_value))

        return value

    def substitute_in_dict(self, d: Dict) -> Dict:
        """Recursively substitute variables in dictionary."""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = self.substitute_in_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.substitute_in_dict(item) if isinstance(item, dict)
                    else self.substitute_variables(item)
                    for item in value
                ]
            else:
                result[key] = self.substitute_variables(value)
        return result

    def call_agent(self, agent_id: str, input_data: Dict) -> str:
        """Call an agent on Claude Platform and return its response."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(input_data)
                }
            ]
        }

        logger.info(f"Calling agent {agent_id}...")
        response = requests.post(
            f"{CLAUDE_PLATFORM_API}/agents/{agent_id}/messages",
            json=payload,
            headers=headers,
            timeout=300,
        )

        if response.status_code == 401:
            raise ValueError("Unauthorized: Check your CLAUDE_API_KEY")

        response.raise_for_status()
        result = response.json()

        # Extract the agent's response
        if "content" in result:
            return result["content"][0].get("text", "")
        return json.dumps(result)

    def call_local_agent(self, agent_type: str, input_data: Dict) -> str:
        """Call a local/built-in agent (e.g., web_search, web_fetch)."""
        if agent_type == "web_search":
            return self.web_search(input_data.get("query", ""))
        elif agent_type == "web_fetch":
            return self.web_fetch(input_data.get("url", ""))
        elif agent_type == "delay":
            import time
            seconds = input_data.get("seconds", 0)
            logger.info(f"Delaying for {seconds} seconds...")
            time.sleep(seconds)
            return "Delay complete"
        else:
            raise ValueError(f"Unknown local agent type: {agent_type}")

    def web_search(self, query: str) -> str:
        """Mock web search (replace with real implementation)."""
        logger.info(f"Searching: {query}")
        # TODO: Implement real web search (e.g., Google Custom Search, Bing, etc)
        return f"Search results for: {query}"

    def web_fetch(self, url: str) -> str:
        """Fetch content from a URL."""
        logger.info(f"Fetching: {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return response.text[:1000]  # Limit to 1000 chars
        except Exception as e:
            return f"Error fetching {url}: {e}"

    def execute_step(self, step_idx: int, step: Dict[str, Any]) -> Any:
        """Execute a single workflow step."""
        step_name = step.get("name", f"Step {step_idx}")
        agent = step.get("agent")
        input_data = step.get("input", {})

        logger.info(f"\n📍 Step {step_idx}: {step_name}")
        logger.info(f"   Agent: {agent}")

        # Substitute variables in input
        input_data = self.substitute_in_dict(input_data)
        logger.info(f"   Input: {json.dumps(input_data, indent=4)}")

        # Call agent
        if agent.startswith("agent:"):
            # Call Claude Platform agent
            agent_id = agent.replace("agent:", "").strip()
            output = self.call_agent(agent_id, input_data)
        else:
            # Call local/built-in agent
            output = self.call_local_agent(agent, input_data)

        # Store output for next steps
        self.step_outputs[step_idx] = output

        logger.info(f"   Output: {str(output)[:200]}...")
        return output

    def execute(self, workflow_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """Execute entire workflow."""
        logger.info(f"📋 Loading workflow: {workflow_path}")
        self.load_workflow(workflow_path)

        workflow_name = self.workflow_data.get("name", "Unnamed Workflow")
        logger.info(f"🚀 Starting: {workflow_name}")

        if dry_run:
            logger.info("🔍 DRY RUN MODE - No agents will be called\n")

        steps = self.workflow_data.get("steps", [])

        try:
            for step_idx, step in enumerate(steps):
                if dry_run:
                    logger.info(f"\n📍 Step {step_idx}: {step.get('name', 'Unnamed')}")
                    logger.info(f"   Agent: {step.get('agent')}")
                    input_data = self.substitute_in_dict(step.get("input", {}))
                    logger.info(f"   Input: {json.dumps(input_data, indent=4)}")
                else:
                    self.execute_step(step_idx, step)

            logger.info(f"\n✅ Workflow completed: {workflow_name}")
            return {
                "status": "success",
                "workflow": workflow_name,
                "steps_executed": len(steps),
                "outputs": self.step_outputs
            }

        except Exception as e:
            logger.error(f"\n❌ Workflow failed: {e}")
            return {
                "status": "failed",
                "workflow": workflow_name,
                "error": str(e),
                "outputs": self.step_outputs
            }


def main():
    parser = argparse.ArgumentParser(
        description="Execute Claude Platform agent workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 workflow_runner.py workflows/daily-linkedin-post.yaml
  python3 workflow_runner.py workflows/daily-linkedin-post.yaml --dry-run
  python3 workflow_runner.py workflows/*.yaml
        """,
    )
    parser.add_argument(
        "workflow",
        help="Workflow YAML file to execute",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview workflow without executing agents",
    )
    parser.add_argument(
        "--api-key",
        help="Claude Platform API key (uses CLAUDE_API_KEY env var if not set)",
    )

    args = parser.parse_args()

    try:
        executor = WorkflowExecutor(api_key=args.api_key)
        result = executor.execute(args.workflow, dry_run=args.dry_run)

        if result["status"] == "failed":
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
