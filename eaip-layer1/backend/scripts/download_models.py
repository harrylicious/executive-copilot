"""Download required NLP models for the GraphRAG pipeline.

Usage:
    python -m spacy download en_core_web_sm

Or via the project script entry point:
    download-models
"""

import subprocess
import sys


def main():
    """Download the spaCy English language model required for entity extraction."""
    print("Downloading spaCy en_core_web_sm model...")
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        check=False,
    )
    if result.returncode != 0:
        print("Failed to download spaCy model. Please run manually:")
        print("  python -m spacy download en_core_web_sm")
        sys.exit(1)
    print("Model download complete.")


if __name__ == "__main__":
    main()
