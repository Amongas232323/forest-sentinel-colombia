"""Post-procesa una migración autogenerada para que los enums compartidos de PostgreSQL
se creen una sola vez (explícitamente) y no una vez por tabla. Uso:
    python scripts/fix_enum_migration.py migrations/versions/<file>.py
"""

import re
import sys
from pathlib import Path

ENUM_RE = re.compile(r"sa\.Enum\(((?:'[^']+', )*'[^']+'), name='(\w+)'\)")


def main(path: str) -> None:
    p = Path(path)
    s = p.read_text()
    enums = {m.group(2): m.group(1) for m in ENUM_RE.finditer(s)}
    s = ENUM_RE.sub(lambda m: f"postgresql.ENUM(name='{m.group(2)}', create_type=False)", s)
    if "from sqlalchemy.dialects import postgresql" not in s:
        s = s.replace("from alembic import op\n", "from alembic import op\nfrom sqlalchemy.dialects import postgresql\n", 1)
    pre = "\n".join(f"    postgresql.ENUM({v}, name='{k}').create(bind, checkfirst=True)" for k, v in enums.items())
    s = s.replace(
        "def upgrade() -> None:\n",
        "def upgrade() -> None:\n    bind = op.get_bind()\n"
        "    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')\n"
        "    op.execute('CREATE SEQUENCE IF NOT EXISTS alert_number_seq START 1')\n" + pre + "\n",
        1,
    )
    drops = "\n".join(f"    postgresql.ENUM(name='{k}').drop(op.get_bind(), checkfirst=True)" for k in enums)
    s = s.rstrip() + "\n" + drops + "\n    op.execute('DROP SEQUENCE IF EXISTS alert_number_seq')\n"
    p.write_text(s)
    print(f"patched {len(enums)} enums in {p.name}")


if __name__ == "__main__":
    main(sys.argv[1])
