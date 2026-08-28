from financial_charts.template.models import Currency

_CURRENCY_BY_CODE = {"USD": Currency.USD, "ILS": Currency.ILS}

# TASE quotes report in agorot (1/100 shekel); the adapter divides by 100 at the
# value level before tagging a point ILS, so nothing downstream ever sees "ILA".
AGOROT_CODE = "ILA"


def map_currency(code: str | None) -> Currency | None:
    """Map a source's raw currency code to the template's `Currency`.

    Returns `None` for an unrecognized/missing code so callers can degrade the
    metric to "no data available" rather than guessing a currency.
    """
    if code == AGOROT_CODE:
        return Currency.ILS
    return _CURRENCY_BY_CODE.get(code or "")
