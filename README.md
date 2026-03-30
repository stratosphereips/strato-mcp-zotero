# Stratosphere MCP Zotero

A Python MCP server that connects your Zotero library to AI assistants. Rather than exposing raw API endpoints, it offers a small set of tools shaped around how researchers actually work: finding sources, browsing collections, inspecting items, and saving or updating metadata.

Works with Claude, Gemini CLI, OpenAI Codex, and any MCP-compatible client.

## MCP Agent Stories

This server is built around how researchers use Zotero, not around the API surface. Instead of exposing raw endpoints, it offers five tools shaped by real workflows:

1. **Find sources** - `find_library_sources` searches your library by keyword, DOI, or author and returns compact summaries with optional collection context. The natural starting point for any research question.
2. **Inspect a source** - Once you have an item key, `inspect_saved_source` returns its full normalized metadata. Useful for checking what's already saved before adding a duplicate.
3. **Browse a collection** - `review_collection` resolves a collection by name or key, summarizes it, and lists its top items (plus child collections if you ask). Good for "what do I have on X?"
4. **Save a source** - `save_source_to_library` takes a title, creators, tags, and collection assignments and adds the item to your library, returning a summary of what was saved.
5. **Update metadata** - `update_saved_source` patches only the fields you provide: fix a DOI, add tags, move to a different collection, without touching anything else.

Collection arguments accept either a name or a key. If a name is ambiguous, the tool returns candidates so the agent can resolve it.

For `save_source_to_library` and `update_saved_source`, use `;` to separate creators and `,` for tags:

```
creators="Ada Lovelace; Grace Hopper"
creators="author: Turing, Alan; editor: Knuth, Donald"
tags="reading-queue, llm, bibliography"
```

## Prerequisites

**Zotero API key:**

1. Go to your Zotero account settings → API Keys
2. Create a key with the library permissions you need
3. Copy it into your `.env` file

**Target library:**

- Set `ZOTERO_LIBRARY_TYPE=user` for your personal library or `group` for a group library.
- `ZOTERO_LIBRARY_ID` is the numeric group ID from `zotero.org/groups/<ID>/…`. Required for group libraries, optional for personal ones (auto-resolved from the key).
- Make sure the API key has access to the library you specify (group and personal permissions are separate).

## Quick start (Docker)

```bash
# Build
docker compose build

# Configure
cp .env.example .env
# Fill in ZOTERO_API_KEY, then lock down the file:
chmod 600 .env
```

**Register with your AI assistant:**

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

Use the full path to your `.env` file. Claude Desktop launches Docker from an unknown working directory, so relative paths won't work.

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

Edit `~/.gemini/settings.json` (or `.gemini/settings.json` in your project root):

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

</details>

<details>
<summary><strong>OpenAI Codex</strong></summary>

Edit `~/.codex/config.toml` (or `.codex/config.toml` in your project root):

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

</details>

## FAQ

**Why can't one MCP instance talk to multiple Zotero libraries?**

Zotero's API scopes every request to a single library (either `/users/<id>` or `/groups/<id>`) based on the key you configure. Each running instance is bound to one `ZOTERO_LIBRARY_TYPE`/`ZOTERO_LIBRARY_ID` pair at startup. To work with multiple libraries simultaneously, run one MCP instance per library (each with its own env file), or build a dispatcher that routes requests to different instances.
