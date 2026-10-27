"""Export the actual API's OpenAPI contract without a DB connection or local secrets."""

import json
from pathlib import Path

from clearledger.config import Settings
from clearledger.main import create_app


def main():
    app = create_app(Settings(_env_file=None, database_url="postgresql+psycopg://unused/unused"))
    path = Path("local-data/frontend-openapi.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf8")
    print("Exported actual API contract to", path)


if __name__ == "__main__":
    main()
