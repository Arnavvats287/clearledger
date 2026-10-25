"""Local nonfinancial outbox/workflow host. No Redis or financial mutation tools."""

import argparse
import json
import time

from clearledger.case_outbox import drain
from clearledger.config import Settings
from clearledger.db import build_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    settings = Settings()
    if settings.organization_id is None:
        raise SystemExit("ORGANIZATION_ID required")
    engine = build_engine(settings.database_url)
    try:
        while True:
            print(
                json.dumps(drain(engine, settings.organization_id, settings, args.limit)),
                flush=True,
            )
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
