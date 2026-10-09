"""Check one translation: python -m tqe --lang es --source "..." --target "..." """

import argparse
import json
import sys

from tqe.checks import LANGUAGES, check

parser = argparse.ArgumentParser(prog="python -m tqe", description="Check one clinical translation.")
parser.add_argument("--lang", required=True, choices=LANGUAGES)
parser.add_argument("--source", required=True, help="English source sentence")
parser.add_argument("--target", required=True, help="Translated sentence")
args = parser.parse_args()

result = check(args.source, args.target, args.lang)
print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
sys.exit(1 if result.verdict == "FAIL" else 0)
