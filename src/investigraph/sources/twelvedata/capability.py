from investigraph.sources.base import Capability
from investigraph.template.models import Market, Period

# Twelve Data (paid tier): full US + TASE coverage with 10y history, metered by API credits.
CAPABILITY = Capability(
    markets={Market.US, Market.TASE},
    periods={Period.ANNUAL, Period.QUARTERLY, Period.TTM},
    # TTM is derived from the trailing four quarters (template/trailing.py's
    # derive_ttm_fundamentals), so it needs the same history depth as QUARTERLY.
    max_history={Period.ANNUAL: 10, Period.QUARTERLY: 10, Period.TTM: 10},
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
