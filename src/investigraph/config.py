import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_RANGE = "5y"
DEFAULT_CHART_SET = "fundamentals"


def data_source_name() -> str:
    return os.environ.get("DATA_SOURCE", "twelvedata").strip()
