import argparse

from financial_charts.web.app import create_app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="financial_charts.web",
        description="Local web UI for Financial Charts (dev server, not for production).",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    # threaded=False: the render path uses matplotlib's pyplot, which is not
    # thread-safe; this is a single-user local tool that needs no concurrency.
    create_app().run(host=args.host, port=args.port, threaded=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
