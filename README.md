# Stratosphere MCP Zotero

A Python MCP server that connects your Zotero library to AI assistants. Rather than exposing raw API endpoints, it offers a small set of tools shaped around how researchers actually work: finding sources, browsing collections, inspecting items, and saving or updating metadata.

Works with Claude, Gemini CLI, OpenAI Codex, and any MCP-compatible client.

## MCP Agent Stories

This server is built around how researchers use Zotero, not around the API surface. It supports your personal library and any group libraries your API key can access — all from a single MCP instance.

### Discovering sources

**"Find papers about deception in the 'Deception Research' group"**
The agent calls `list_libraries` to resolve the group name, then `find_library_sources` with `library="Deception Research"` to return matching items with compact summaries.

**"Do I have any paper about bananas in 'Exotic Research' or my personal library?"**
The agent calls `search_across_libraries` with `libraries="Exotic Research, personal"` and gets results from both in a single response.

**"Do I already have this DOI saved?"**
`find_library_sources` accepts a DOI as the query and checks if it exists anywhere in the target library.

### Browsing and inspecting

**"What's in my Reading Queue collection?"**
`review_collection` resolves the collection by name, summarizes it, and lists its top items. Pass `library="Group Name"` to look inside a group library instead.

**"Show me the full metadata for item ABCD1234"**
`inspect_saved_source` returns normalized metadata for a known item key. Add `include_raw=true` to see the full Zotero API payload.

### Saving and updating

**"Save this paper to my library under the 'LLM' collection"**
`save_source_to_library` takes a title, creators, tags, and collection assignments and adds the item, returning a summary of what was saved. Specify `library` to save into a group instead.

**"Fix the DOI on item ABCD1234 and add the tag 'to-read'"**
`update_saved_source` patches only the fields you provide, leaving everything else untouched.

---

Use `;` to separate creators and `,` for tags in save/update calls:

```
creators="Ada Lovelace; Grace Hopper"
creators="author: Turing, Alan; editor: Knuth, Donald"
tags="reading-queue, llm, bibliography"
```

Collection and library arguments accept either a name or a key. If a name is ambiguous, the tool returns candidates so the agent can resolve it.

## Prerequisites

**Zotero API key:**

1. Go to your Zotero account settings → API Keys
2. Create a key with the library permissions you need (personal and/or group access)
3. Copy it into your `.env` file

The server automatically resolves your user ID and all accessible group libraries from the API key — no manual library IDs required.

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
