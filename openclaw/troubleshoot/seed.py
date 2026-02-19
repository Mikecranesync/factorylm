"""CLI: Load JSON troubleshoot trees from trees/ directory into the database.

Usage:
    python -m openclaw.troubleshoot.seed
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from openclaw.troubleshoot.store import create_schema, upsert_tree

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TREES_DIR = Path(__file__).parent / "trees"


def seed_all() -> int:
    """Create schema and load all JSON tree files into the database.

    Returns the number of trees loaded.
    """
    create_schema()

    loaded = 0
    for json_file in sorted(TREES_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            tree_id = upsert_tree(data)
            if tree_id is not None:
                logger.info("Seeded %s -> tree_id=%d", json_file.name, tree_id)
                loaded += 1
            else:
                logger.error("Failed to seed %s", json_file.name)
        except Exception:
            logger.exception("Error loading %s", json_file.name)

    logger.info("Seeded %d / %d trees", loaded, len(list(TREES_DIR.glob("*.json"))))
    return loaded


if __name__ == "__main__":
    count = seed_all()
    sys.exit(0 if count > 0 else 1)
