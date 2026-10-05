# Workflow System for Claude Platform Agents

Orchestrate Claude Platform agents by chaining them together in YAML workflows. Automate multi-agent tasks, scheduled jobs, and complex agent pipelines without code.

## Quick Start

### 1. Install Dependencies

```bash
pip install pyyaml requests
```

### 2. Set Your API Key

```bash
export CLAUDE_API_KEY="sk-..."
```

### 3. Create a Workflow

Create a YAML file describing your agent workflow:

```yaml
# workflows/my-workflow.yaml
name: "My Agent Workflow"

steps:
  - name: "Search for data"
    agent: "web_search"
    input:
      query: "What is AI?"
  
  - name: "Write about it"
    agent: "agent:AGENT_ID_HERE"
    input:
      topic: "{{ steps[0].output }}"
```

### 4. Run It

```bash
python3 workflow_runner.py workflows/my-workflow.yaml
```

### Preview Before Running (Dry-Run)

```bash
python3 workflow_runner.py workflows/my-workflow.yaml --dry-run
```

## Workflow YAML Format

### Basic Structure

```yaml
name: "Workflow Name"
description: "What this workflow does"

variables:
  key1: "value1"
  key2: "value2"

steps:
  - name: "Step Name"
    agent: "agent_type_or_id"
    input:
      param1: "value"
      param2: "{{ steps[0].output }}"

schedule:
  cron: "0 9 * * *"  # Optional: Daily at 9am
  timezone: "UTC"

notifications:
  on_success: "Message"
  on_failure: "Message"
  webhook: "{{ env.WEBHOOK_URL }}"
```

### Step Configuration

Each step has:

- **name** (required) — Human-readable step name
- **agent** (required) — Agent to call
- **input** (required) — Input parameters for the agent

```yaml
steps:
  - name: "My Step"
    agent: "agent:AGENT_ID"
    input:
      param1: "literal value"
      param2: "{{ steps[0].output }}"  # Reference previous output
      param3: "{{ env.VAR_NAME }}"      # Environment variables
      param4: "{{ workflow.key }}"       # Workflow variables
```

## Agent Types

### Claude Platform Agents

Call agents deployed to Claude Platform:

```yaml
steps:
  - name: "Call my agent"
    agent: "agent:AGENT_ID"
    input:
      message: "Hello"
```

**Get your AGENT_ID:**
1. Deploy agent with `deploy.py`
2. Check https://console.anthropic.com/agents
3. Copy the ID from the URL

### Built-in Agents

Reusable agent types for common tasks:

#### `web_search`
Search the web for information:

```yaml
- name: "Search for AI trends"
  agent: "web_search"
  input:
    query: "latest AI breakthroughs 2025"
```

#### `web_fetch`
Fetch and read content from a URL:

```yaml
- name: "Get article"
  agent: "web_fetch"
  input:
    url: "https://example.com/article"
```

#### `delay`
Pause execution:

```yaml
- name: "Wait 5 seconds"
  agent: "delay"
  input:
    seconds: 5
```

## Variable Substitution

Pass data between steps using `{{ }}` templates.

### From Previous Steps

```yaml
steps:
  - name: "Step 1"
    agent: "web_search"
    input:
      query: "AI news"
  
  - name: "Step 2"
    agent: "agent:AGENT_ID"
    input:
      content: "{{ steps[0].output }}"  # Use output from step 0
      summary: "{{ steps[1].output }}"  # Or any earlier step
```

### From Environment Variables

```yaml
steps:
  - name: "Post to service"
    agent: "agent:AGENT_ID"
    input:
      api_key: "{{ env.API_KEY }}"
      webhook: "{{ env.WEBHOOK_URL }}"
```

### From Workflow Variables

```yaml
variables:
  brand_name: "My Company"
  tone: "professional"

steps:
  - name: "Generate content"
    agent: "agent:AGENT_ID"
    input:
      brand: "{{ workflow.brand_name }}"
      style: "{{ workflow.tone }}"
```

## Examples

### Daily LinkedIn Post Workflow

```yaml
name: "Daily LinkedIn Story"

steps:
  - name: "Find trending topic"
    agent: "web_search"
    input:
      query: "AI disruption trends today"
  
  - name: "Write LinkedIn post"
    agent: "agent:AGENT_ID"
    input:
      topic: "{{ steps[0].output }}"
      max_length: 300
  
  - name: "Post to LinkedIn"
    agent: "agent:LINKEDIN_AGENT_ID"
    input:
      content: "{{ steps[1].output }}"
      profile: "my-company"

schedule:
  cron: "0 9 * * *"  # Daily 9am
```

### Multi-Agent Content Pipeline

```yaml
name: "Content Creation Pipeline"

steps:
  - name: "Research"
    agent: "web_search"
    input:
      query: "{{ workflow.topic }}"
  
  - name: "Outline"
    agent: "agent:OUTLINE_AGENT"
    input:
      research: "{{ steps[0].output }}"
  
  - name: "Write article"
    agent: "agent:WRITER_AGENT"
    input:
      outline: "{{ steps[1].output }}"
      length: "long"
  
  - name: "Create summary"
    agent: "agent:SUMMARIZER_AGENT"
    input:
      article: "{{ steps[2].output }}"
      length: "short"
  
  - name: "Generate social posts"
    agent: "agent:SOCIAL_AGENT"
    input:
      article: "{{ steps[2].output }}"
      platforms: ["linkedin", "twitter"]
```

## Running Workflows

### One-Time Execution

```bash
python3 workflow_runner.py workflows/my-workflow.yaml
```

### Dry-Run (Preview)

```bash
python3 workflow_runner.py workflows/my-workflow.yaml --dry-run
```

Shows exactly what will be sent to agents without calling them.

### Multiple Workflows

```bash
python3 workflow_runner.py workflows/*.yaml
```

### With Custom API Key

```bash
python3 workflow_runner.py workflows/my-workflow.yaml --api-key "sk-..."
```

## Scheduling Workflows

Workflows can be scheduled to run automatically.

### Cron Syntax

```yaml
schedule:
  cron: "0 9 * * *"      # Daily at 9am UTC
  timezone: "UTC"        # Optional
```

**Common patterns:**
- `0 9 * * *` — Daily at 9am
- `0 */6 * * *` — Every 6 hours
- `0 9 * * 1-5` — Weekdays at 9am
- `0 9 * * 0,6` — Weekends at 9am
- `0 9 1 * *` — First day of month at 9am

### Setup Scheduling

**Option 1: Cron Job (Linux/Mac)**

```bash
# Add to crontab
crontab -e

# Add this line:
0 9 * * * cd /path/to/claude-skills-library && python3 workflows/workflow_runner.py workflows/daily-post.yaml
```

**Option 2: Using a Process Manager**

See `workflow_scheduler.py` (coming soon) for automated scheduling.

## Notifications

Get alerts when workflows succeed or fail:

```yaml
notifications:
  on_success: "✅ Post published!"
  on_failure: "❌ Failed to publish"
  webhook: "{{ env.SLACK_WEBHOOK }}"
```

## Troubleshooting

### "CLAUDE_API_KEY environment variable not set"

```bash
export CLAUDE_API_KEY="your-key-here"
```

### "Agent not found" or "401 Unauthorized"

- Check your AGENT_ID is correct
- Verify agent was deployed successfully via `deploy.py`
- Check API key has permission to access the agent

### Variables Not Substituting

Variable templates must be exact:
- ✅ `{{ steps[0].output }}`
- ❌ `{{ steps[0] }}`
- ❌ `{{ step 0 output }}`

### Workflow Stops on First Step

Each step must complete successfully. If a step fails:
1. Check the agent exists
2. Check the input parameters
3. Try `--dry-run` to preview the exact input being sent

## API Reference

### WorkflowExecutor Class

```python
from workflow_runner import WorkflowExecutor

executor = WorkflowExecutor(api_key="sk-...")
result = executor.execute("workflows/my-workflow.yaml")
```

**Returns:**
```json
{
  "status": "success",
  "workflow": "Workflow Name",
  "steps_executed": 3,
  "outputs": {
    "0": "output from step 0",
    "1": "output from step 1"
  }
}
```

## Next Steps

- Deploy your first agent with `agents/deploy.py`
- Create a workflow YAML that chains agents
- Schedule it to run automatically
- Build a UI on top (future feature)
