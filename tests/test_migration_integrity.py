"""
test_migration_integrity.py
Validates the Alembic migration revision chain without a live database.
Catches: orphaned revisions, broken down_revision links, branched history,
         missing head, multiple bases.
"""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = PROJECT_ROOT / "migrations" / "versions"


def _load_revision_map() -> dict[str, str | None]:
    """
    Parse revision ID and down_revision from every .py file in versions/.
    Returns: {revision_id: down_revision_or_None}
    """
    revisions: dict[str, str | None] = {}

    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text()
        rev_id = None
        down_rev_raw = "None"

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("revision ="):
                rev_id = stripped.split("=", 1)[1].strip().strip("'\"")
            elif stripped.startswith("down_revision ="):
                down_rev_raw = stripped.split("=", 1)[1].strip().strip("'\"")

        if rev_id:
            down_rev = None if down_rev_raw in ("None", "") else down_rev_raw
            revisions[rev_id] = down_rev

    return revisions


def test_migrations_directory_exists():
    assert VERSIONS_DIR.is_dir(), f"migrations/versions/ not found at {VERSIONS_DIR}"


def test_at_least_one_migration_exists():
    revisions = _load_revision_map()
    assert len(revisions) >= 1, "No migration files found in migrations/versions/"


def test_migration_chain_has_no_broken_down_revision():
    """Every down_revision must point to an existing revision ID (or be None)."""
    revisions = _load_revision_map()
    all_ids = set(revisions.keys())

    broken = {}
    for rev_id, down_rev in revisions.items():
        if down_rev is not None and down_rev not in all_ids:
            broken[rev_id] = down_rev

    assert not broken, (
        "Migration(s) with unknown down_revision:\n"
        + "\n".join(f"  {rid} -> {dr}" for rid, dr in broken.items())
    )


def test_migration_chain_has_single_base():
    """Exactly one migration must have down_revision=None (the initial migration)."""
    revisions = _load_revision_map()
    bases = [rid for rid, dr in revisions.items() if dr is None]

    assert len(bases) == 1, (
        f"Expected exactly 1 base migration, found {len(bases)}: {bases}\n"
        "Branched history or duplicate initial migration."
    )


def test_migration_chain_has_single_head():
    """Exactly one migration must have no successor (the current head)."""
    revisions = _load_revision_map()
    all_ids = set(revisions.keys())
    referenced_as_base = {dr for dr in revisions.values() if dr is not None}
    heads = all_ids - referenced_as_base

    assert len(heads) == 1, (
        f"Expected exactly 1 head revision, found {len(heads)}: {heads}\n"
        "Branched history or unmerged migration branches."
    )


def test_migration_chain_is_fully_reachable_from_head():
    """
    Walk from head -> base through down_revision links.
    Every migration must be reachable — no orphaned islands.
    """
    revisions = _load_revision_map()
    all_ids = set(revisions.keys())
    referenced_as_base = {dr for dr in revisions.values() if dr is not None}
    heads = all_ids - referenced_as_base

    assert len(heads) == 1, "Skipped: no single head (covered by single_head test)"

    head = next(iter(heads))

    visited = set()
    current = head
    while current is not None:
        if current in visited:
            raise AssertionError(f"Cycle detected at revision {current}")
        visited.add(current)
        current = revisions.get(current)

    unreachable = all_ids - visited
    assert not unreachable, (
        f"Orphaned migration(s) not reachable from head ({head}): {unreachable}"
    )


def test_each_migration_file_has_upgrade_and_downgrade():
    """Every migration file must define both upgrade() and downgrade()."""
    missing = []
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text()
        if "def upgrade" not in text or "def downgrade" not in text:
            missing.append(path.name)

    assert not missing, (
        "Migration file(s) missing upgrade() or downgrade():\n"
        + "\n".join(f"  {f}" for f in missing)
    )