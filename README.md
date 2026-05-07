# Stratosphere MCP Zotero

Connect your Zotero library to an AI assistant. Ask questions, find papers, save sources, fix metadata — in plain language.

Works with Claude, Gemini CLI, OpenAI Codex, and any other MCP client.

## What you can ask

You ask in plain language. The assistant picks the right tool. You stay in your normal chat.

### Find a paper

> "Find papers about deception in the Deception Research group."
> "Do I have anything by Kahneman in my ML collection?"
> "Do I already have this DOI?"
> "Find the paper with BibTeX key smith2023."

The assistant searches your library and returns a short list with title, authors, year, and DOI.

### Search several libraries at once

> "Do I have anything about bananas in Exotic Research or my personal library?"

You get one answer with results from both.

### Browse by tag or collection

> "Show me everything tagged 'to-read'."
> "What's in my Reading Queue collection?"
> "List all papers tagged 'important' in the Deception Research group."

The assistant lists the items. Tags must match exactly.

### Look up one item

> "Show me the full details for item ABCD1234."
> "Where is the PDF for this paper on my disk?"

You get normalised metadata, or a local PDF path you can open in your editor.

### Count your library

> "How many papers do I have in my personal Zotero?"
> "How big is the Deception Research group library?"

You get a number. By default it counts top-level items only, not PDFs and notes.

### Save and update

> "Save this paper to my Reading Queue collection."
> "Fix the DOI on item ABCD1234 and add the tag 'to-read'."

The assistant adds or updates the item and shows you what changed. Only the fields you mention are touched — nothing else is overwritten.

---

### A few things to know

- **Group libraries:** All tools accept a `library` argument — `"personal"`, a group name like `"Deception Research"`, or a numeric group ID. Group names are fuzzy-matched.
- **Collections by name:** Pass a collection name and the tool resolves it. If two collections have similar names, the tool asks you to pick.
- **Save/update format:** Separate authors with `;` and tags with `,`.
  ```
  creators="Ada Lovelace; Grace Hopper"
  creators="author: Turing, Alan; editor: Knuth, Donald"
  tags="reading-queue, llm, bibliography"
  ```
- **Pagination:** Tools that list items (`find_library_sources`, `find_by_tag`) cap at 100 results per call. Use the `offset` argument to page through larger sets — `total_results` in the response tells you when to stop.
- **BibTeX keys:** Looking up a paper by its citation key requires the [Better BibTeX](https://retorque.re/zotero-better-bibtex/) Zotero plugin, which writes the key into the item's `extra` field.

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
