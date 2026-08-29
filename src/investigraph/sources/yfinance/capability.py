from investigraph.sources.base import Capability
from investigraph.template.models import Market, Period

# yfinance (free tier): strong US coverage, TASE prices work but fundamentals are
# sparse/inconsistent per-ticker (see CLAUDE.md "TASE unit trap" and gotchas). The
# adapter marks individual metrics unavailable per-ticker; this declaration is about
# what the source can supply in general, not a per-ticker guarantee.
CAPABILITY = Capability(
    markets={Market.US, Market.TASE},
    periods={Period.ANNUAL, Period.QUARTERLY, Period.TTM},
    # QUARTERLY verified live 2026-08-29 (commission-source, AAPL/JPM/OXM/POLI.TA/
    # TEVA.TA/ORL.TA): yfinance's quarterly_income_stmt/quarterly_cashflow/
    # quarterly_balance_sheet return only ~5 columns (~1y), not the 4y this
    # previously claimed — that number predates this measurement and was never
    # actually checked against live data before now. TTM is derived from the
    # trailing four quarters (template/trailing.py's derive_ttm_fundamentals), so
    # it needs the same history depth as QUARTERLY.
    max_history={Period.ANNUAL: 4, Period.QUARTERLY: 1, Period.TTM: 1},
    metrics={
        "price",
        "revenue",
        "net_income",
        "free_cash_flow",
        "eps",
        "gross_margin",
        "net_margin",
        "ebitda",
        "research_and_development",
        "selling_general_administrative",
        "dividends_paid",
        "shares_outstanding",
        "ebit",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "cash_and_equivalents",
        "total_debt",
        "total_current_assets",
        "total_current_liabilities",
    },
)
