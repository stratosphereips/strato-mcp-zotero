# Stratosphere MCP Zotero

A Python MCP server that exposes Zotero as a small set of research-library workflows for AI assistants. Instead of mirroring raw Zotero endpoints, it is designed around common agent stories like finding sources, reviewing a collection, inspecting one saved source, and saving or updating library metadata.

Compatible with Claude, Gemini CLI, OpenAI Codex, and any MCP-compatible client.


## Prerequisites

Create a Zotero API key:

1. Open your Zotero account settings
2. Go to the API Keys section
3. Create a dedicated key with the library permissions you want this MCP to use
4. Copy the key into your `.env` in the next step

Choose a target library:

1. Set `ZOTERO_LIBRARY_TYPE=user` for your personal library or `group` for a group library.
2. The `ZOTERO_LIBRARY_ID` must be the group’s **numeric ID** (from `https://www.zotero.org/groups/<ID>/…`) whenever `ZOTERO_LIBRARY_TYPE=group`; it is optional for `user`, because personal libraries are auto-resolved from the key.
3. Ensure the API key you use has access to the specified library (groups have separate permissions from personal libraries).


## Quick start (Docker)

### Step 1: Build

```bash
docker compose build
```

### Step 2: Configure

```bash
cp .env.example .env
# Fill in ZOTERO_API_KEY
```

> This file contains your API key in plain text. Restrict its permissions:
> `chmod 600 .env`

### Step 3: Register with your AI assistant

<details>
<summary><strong>Claude</strong></summary>

**Claude Desktop** — edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env-file", "/absolute/path/to/.env",
        "zotero-mcp:latest",
        "serve"
      ]
    }
  }
}
```

Replace `/absolute/path/to/.env` with the full path to your `.env` file. Claude Desktop
launches Docker from an unspecified working directory, so relative paths do not work.

**Claude Code:**

```bash
claude mcp add --transport stdio zotero -- \
  docker run --rm -i \
    --env-file /absolute/path/to/.env \
    zotero-mcp:latest serve
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

Edit `~/.gemini/settings.json` (or `.gemini/settings.json` in your project root for project-scoped config):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "--env-file", "/absolute/path/to/.env",
        "zotero-mcp:latest",
        "serve"
      ]
    }
  }
}
```

Replace `/absolute/path/to/.env` with the full path to your `.env` file.

</details>

<details>
<summary><strong>OpenAI Codex</strong></summary>

Edit `~/.codex/config.toml` (or `.codex/config.toml` in your project root for project-scoped config):

```toml
[[mcp_servers]]
name = "zotero"
command = "docker"
args = [
  "run", "--rm", "-i",
  "--env-file", "/absolute/path/to/.env",
  "zotero-mcp:latest",
  "serve"
]
```

Replace `/absolute/path/to/.env` with the full path to your `.env` file.

</details>


## Alternative: local install (without Docker)

### Step 1: Install

```bash
git clone https://github.com/stratosphereips/strato-mcp-zotero
cd strato-mcp-zotero
uv venv && source .venv/bin/activate
uv pip install -e .
```

### Step 2: Configure

```bash
cp .env.example .env
# Fill in ZOTERO_API_KEY
```

> This file contains your API key in plain text. Restrict its permissions:
> `chmod 600 .env`

### Step 3: Register with your AI assistant

<details>
<summary><strong>Claude</strong></summary>

**Claude Desktop** — edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

> This file will contain your API key in plain text. Restrict its permissions
> after editing: `chmod 600 ~/Library/Application\ Support/Claude/claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "zotero": {
      "command": "/absolute/path/.venv/bin/zotero-mcp",
      "env": {
        "ZOTERO_API_KEY": "your_api_key"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add zotero /absolute/path/.venv/bin/zotero-mcp \
  --env-file /absolute/path/to/.env
```

</details>

<details>
<summary><strong>Gemini CLI</strong></summary>

Edit `~/.gemini/settings.json` (or `.gemini/settings.json` in your project root for project-scoped config):

```json
{
  "mcpServers": {
    "zotero": {
      "command": "/absolute/path/.venv/bin/zotero-mcp",
      "env": {
        "ZOTERO_API_KEY": "your_api_key"
      }
    }
  }
}
```

> This file will contain your API key in plain text. Restrict its permissions
> after editing: `chmod 600 ~/.gemini/settings.json`.

</details>

<details>
<summary><strong>OpenAI Codex</strong></summary>

Edit `~/.codex/config.toml` (or `.codex/config.toml` in your project root for project-scoped config):

```toml
[[mcp_servers]]
name = "zotero"
command = "/absolute/path/.venv/bin/zotero-mcp"

[mcp_servers.env]
ZOTERO_API_KEY = "your_api_key"
```

> This file will contain your API key in plain text. Restrict its permissions
> after editing: `chmod 600 ~/.codex/config.toml`.

</details>


## Tools

The server currently exposes these curated tools:

- `find_library_sources`
- `inspect_saved_source`
- `review_collection`
- `save_source_to_library`
- `update_saved_source`

The workflow is shaped by these stories:

1. **Discover saved sources** – Use `find_library_sources` whenever the agent needs relevant documents for a research question, DOI check, or author filter; the tool returns compact summaries plus optional collection context.
2. **Inspect a known source** – After discovery, call `inspect_saved_source` to surface normalized metadata for a specific Zotero item key, with an optional raw object for deep dives.
3. **Review a collection** – When the user asks “What’s in that collection?”, `review_collection` resolves the name/key, summarizes collection metadata, and returns its top sources (plus child collections when requested).
4. **Save a source** – Provide title, creators (`;`-separated), tags (comma-separated), collections, etc. to `save_source_to_library`, which builds the Zotero payload and reports back the saved summary.
5. **Update metadata** – Use `update_saved_source` to fix DOIs, retitle, add tags, or reassign collections by supplying only the fields that need to change; unchanged parameters stay untouched.

Collection arguments accept either collection names or collection keys. If a name is ambiguous, the tool returns candidate keys so the agent can recover cleanly.

For `save_source_to_library` and `update_saved_source`, creators use `;` as a separator and tags use `,`.
Examples:

- `creators="Ada Lovelace; Grace Hopper"`
- `creators="author: Turing, Alan; editor: Knuth, Donald"`
- `tags="reading-queue, llm, bibliography"`

## FAQ

- **Why can’t one MCP handle every Zotero library I care about?**  
  Zotero locks every request to a single library prefix (`/users/<id>` or `/groups/<id>`) and the API key you provide. Each MCP instance is configured at startup with one `ZOTERO_LIBRARY_TYPE`/`ZOTERO_LIBRARY_ID` plus the matching key, so all tool calls are scoped to that library. Supporting multiple groups simultaneously therefore requires either (a) running one MCP per target library (each Docker/container has its own env file/key) or (b) building a dispatcher that routes the agent to different MCP instances on demand. That’s why one running MCP cannot talk to multiple Zotero libraries at the same time—each deployment is bound to its configured library.
