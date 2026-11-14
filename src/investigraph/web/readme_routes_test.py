import re
from pathlib import Path

from investigraph.web.app import create_app

_README = Path(__file__).resolve().parents[3] / "README.md"


def test_every_route_is_mentioned_in_readme():
    readme = _README.read_text(encoding="utf-8")
    missing = []
    for rule in create_app().url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        # README writes `<id_>`/`<name>` converters in its own words, so compare the
        # static prefix of the path; `/` is checked as the literal "GET /" mention.
        prefix = re.split(r"<", rule.rule)[0].rstrip("/") or "/"
        needle = "GET /`" if prefix == "/" else prefix
        if needle not in readme:
            missing.append(rule.rule)
    assert not missing, f"routes not mentioned in README.md: {missing}"
