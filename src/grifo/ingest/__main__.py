"""Permite `python -m grifo.ingest <dir>` (FR-14)."""

import sys

from grifo.ingest.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
