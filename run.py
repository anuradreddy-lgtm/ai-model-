"""Convenience entry point for running JARVIS from workspace root."""

import sys
from pathlib import Path
import argparse

# Ensure standard output can print Unicode cleanly on Windows console
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project directory is on sys.path even if launched from another drive/folder
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def cli() -> None:
    """Parse CLI options or launch desktop UI."""
    parser = argparse.ArgumentParser(description="JARVIS AI — Windows Desktop Assistant")
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to Ollama and verify model inference without opening UI.",
    )
    args = parser.parse_args()

    if args.test_connection:
        from jarvis.llm.ollama_client import test_ai_connection
        print("Testing local AI connection with Ollama...")
        result = test_ai_connection()
        if result["success"]:
            print(f"[SUCCESS] {result['message']}")
            print(f"  * Active Model: {result['model']}")
            print(f"  * Latency: {result['latency_ms']} ms")
            if "sample_response" in result:
                print(f"  * Sample Output: {result['sample_response']}")
            sys.exit(0)
        else:
            print(f"[ERROR] {result['message']}")
            sys.exit(1)

    from jarvis.main import main
    sys.exit(main())


if __name__ == "__main__":
    cli()
