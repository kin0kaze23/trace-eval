#!/usr/bin/env bash
# Build a standalone binary for trace-eval.
# Usage: ./scripts/build-binary.sh
# Output: dist/trace-eval (single executable, no Python required)
#
# Requires: pip install pyinstaller (or: uv sync --all-extras)

set -euo pipefail

echo "Building trace-eval standalone binary..."

pyinstaller \
    --onefile \
    --name trace-eval \
    --clean \
    --noconfirm \
    --hidden-import trace_eval.judges \
    --hidden-import trace_eval.judges.reliability \
    --hidden-import trace_eval.judges.efficiency \
    --hidden-import trace_eval.judges.retrieval \
    --hidden-import trace_eval.judges.tool_discipline \
    --hidden-import trace_eval.judges.context \
    --hidden-import trace_eval.adapters \
    --hidden-import trace_eval.adapters.claude_code \
    --hidden-import trace_eval.adapters.openclaw \
    --hidden-import trace_eval.adapters.cursor \
    --hidden-import trace_eval.adapters.generic_jsonl \
    --hidden-import trace_eval.adapters.hermes \
    --hidden-import trace_eval.convert \
    --hidden-import trace_eval.remediation \
    --hidden-import trace_eval.autofix \
    --hidden-import trace_eval.locate \
    --hidden-import trace_eval.loader \
    --hidden-import trace_eval.doctor \
    --hidden-import trace_eval.loop \
    trace_eval/cli.py

# Clean up build artifacts
rm -rf build/ trace-eval.spec

# Verify
BINARY="dist/trace-eval"
if [ ! -f "$BINARY" ]; then
    echo "ERROR: Binary not found at $BINARY"
    exit 1
fi

SIZE=$(du -h "$BINARY" | cut -f1)
VERSION=$("$BINARY" --version 2>/dev/null || echo "unknown")

echo ""
echo "✅ Build complete"
echo "   Binary:  $BINARY"
echo "   Size:    $SIZE"
echo "   Version: $VERSION"
echo ""
echo "Test it: $BINARY doctor"
