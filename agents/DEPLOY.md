# Deploying Agents to Claude Platform

Alternative to `ant apply` while the `ant` CLI is unavailable.

## Setup

### 1. Get a Claude Platform API Key

1. Go to https://console.anthropic.com
2. Sign in with your Anthropic account
3. Create or use an existing API key
4. Set it as an environment variable:

```bash
export CLAUDE_API_KEY="sk-..."
```

### 2. Install Python Dependencies

```bash
pip install requests python-frontmatter
```

## Deploy an Agent

### Preview (dry-run)

```bash
python3 agents/deploy.py agents/disruptive-ai-storyteller/ --dry-run
```

Shows what would be sent to the API without actually deploying.

### Deploy to Claude Platform

```bash
python3 agents/deploy.py agents/disruptive-ai-storyteller/
```

**First run:** Creates the agent and saves the ID to `claude-lock.json`  
**Subsequent runs:** Updates the existing agent

### Deploy All Agents

```bash
python3 agents/deploy.py agents/*/
```

### List Deployed Agents

```bash
python3 agents/deploy.py --list
```

Shows all agent IDs from lock files.

## How It Works

1. **Parses** the agent definition (`.md` file with YAML frontmatter + system prompt)
2. **Checks** `claude-lock.json` to see if this agent already exists
3. **Creates or updates** the agent via Claude Platform's `/v1/agents` API
4. **Saves** the agent ID to `claude-lock.json` for future updates

## Environment Variables

- `CLAUDE_API_KEY` (required) — Your Claude Platform API key
- `CLAUDE_PLATFORM_API` (optional) — Defaults to `https://api.claude.com/v1`

## Troubleshooting

**"CLAUDE_API_KEY environment variable not set"**
```bash
export CLAUDE_API_KEY="your-key-here"
```

**"401 Unauthorized"**  
Check that your API key is valid and has permission to create agents.

**"Agent already exists"**  
The agent ID is saved in `claude-lock.json`. To create a new agent, delete that file or the specific entry.

## After Deployment

Your agent will be available at:
```
https://console.anthropic.com/agents/<agent_id>
```

You can then:
- Test it in the console
- Share it with your team
- Integrate it into applications
- Update it by running `deploy.py` again
