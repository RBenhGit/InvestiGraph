from investigraph.sources.base import Capability
from investigraph.template.models import Market, Period

# Twelve Data ("pro" plan tier, confirmed live via /api_usage 2026-08-29 —
# plan_category: "pro", 610 credits/minute; not Ultra/Enterprise). The 10y figure
# below predated any live measurement; a `pro` key genuinely returns only 6y
# annual / ~1y quarterly (confirmed live against JPM/AAPL — a full 12-sample
# commission-source run across both markets exceeds this plan's 610
# credits/minute before finishing all US samples, let alone TASE, so this was
# verified via repeated partial runs rather than one clean commission-source
# pass; re-run commission-source across multiple minutes to fully reconfirm,
# especially the TASE side, before trusting this further). growth_estimates
# (the source for a real analyst 5y growth estimate) is genuinely gated behind
# Ultra/Enterprise on this plan — confirmed live: AAPL alone returns real data
# (Twelve Data's known free/demo-allowlisted symbol on many endpoints), every
# other ticker tested (GOOGL, AMZN, TSLA, META, NVDA, JNJ, V, WMT, TEVA.TA)
# returns 403. Do not wire growth_estimates into valuation/growth.py's
# analyst_estimate_5y_percent slot based on an AAPL-only success.
CAPABILITY = Capability(
    markets={Market.US, Market.TASE},
    periods={Period.ANNUAL, Period.QUARTERLY, Period.TTM},
    # TTM is derived from the trailing four quarters (template/trailing.py's
    # derive_ttm_fundamentals), so it needs the same history depth as QUARTERLY.
    max_history={Period.ANNUAL: 6, Period.QUARTERLY: 1, Period.TTM: 1},
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
