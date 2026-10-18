"""Minimal process entrypoint: deliberately never imports Verifiers or the caller's __main__."""

import json
import sys

from .grading import grade_answer


def main():
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        if len(line) > 2_000_000:
            raise ValueError("Oversized grader request")
        try:
            result = grade_answer(*json.loads(line))
            message = {"grade": result.to_dict()}
        except Exception as error:
            message = {"error": type(error).__name__}
        print(json.dumps(message, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
