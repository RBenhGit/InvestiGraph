from unittest.mock import patch

from investigraph.config import data_source_name


def test_defaults_to_twelvedata():
    with patch.dict("os.environ", {}, clear=True):
        assert data_source_name() == "twelvedata"


def test_reads_data_source_env_var():
    with patch.dict("os.environ", {"DATA_SOURCE": "twelvedata"}):
        assert data_source_name() == "twelvedata"


def test_strips_surrounding_whitespace():
    with patch.dict("os.environ", {"DATA_SOURCE": " twelvedata "}):
        assert data_source_name() == "twelvedata"


def test_env_example_and_readme_show_the_code_default():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    with patch.dict("os.environ", {}, clear=True):
        default = data_source_name()
    assert f"\nDATA_SOURCE={default}\n" in (root / ".env.example").read_text()
    assert f"DATA_SOURCE={default} " in (root / "README.md").read_text()
