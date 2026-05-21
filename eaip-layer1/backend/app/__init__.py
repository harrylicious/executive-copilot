"""Load environment variables from .env file before any settings are constructed."""
from pathlib import Path

from dotenv import load_dotenv

# Resolve .env relative to this file: backend/.env
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")
