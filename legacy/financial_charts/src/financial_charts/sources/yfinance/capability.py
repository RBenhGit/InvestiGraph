from financial_charts.sources.base import Capability
from financial_charts.template.models import Market, Period

# yfinance (free tier): strong US coverage, TASE prices work but fundamentals are
# sparse/inconsistent per-ticker (see CLAUDE.md "TASE unit trap" and gotchas). The
# adapter marks individual metrics unavailable per-ticker; this declaration is about
# what the source can supply in general, not a per-ticker guarantee.
CAPABILITY = Capability(
    markets={Market.US, Market.TASE},
    periods={Period.ANNUAL, Period.QUARTERLY},
    max_history={Period.ANNUAL: 4, Period.QUARTERLY: 4},
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
