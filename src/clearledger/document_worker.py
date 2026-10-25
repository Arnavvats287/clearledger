"""Credential-free bounded parser entry point; stdout is a fixed-code JSON protocol."""

import base64
import json
import sys


def main():
    from clearledger.worker_security import install_guard, posix_limits

    posix_limits()
    from clearledger.document_contract import ExtractionError
    from clearledger.document_parse import parse

    install_guard()
    try:
        request = json.loads(sys.stdin.buffer.read(3_000_000))
        result = parse(base64.b64decode(request["bytes"], validate=True), request["mime"])
    except ExtractionError as error:
        result = {"error": str(error)}
    except Exception:
        result = {"error": "PARSE_FAILED"}
    sys.stdout.write(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
