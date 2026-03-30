#!/bin/sh
set -e

case "$1" in
  serve) exec zotero-mcp ;;
  *)     exec "$@"       ;;
esac
