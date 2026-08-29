from investigraph.web.case_conversion import (
    camel_to_snake,
    keys_to_camel_case,
    keys_to_snake_case,
    snake_to_camel,
)


def test_camel_to_snake_basic():
    assert camel_to_snake("growthRatePercent") == "growth_rate_percent"
    assert camel_to_snake("epsTtm") == "eps_ttm"
    assert camel_to_snake("ruleOneFairValue") == "rule_one_fair_value"
    assert camel_to_snake("id") == "id"
    assert camel_to_snake("ticker") == "ticker"


def test_snake_to_camel_basic():
    assert snake_to_camel("growth_rate_percent") == "growthRatePercent"
    assert snake_to_camel("eps_ttm") == "epsTtm"
    assert snake_to_camel("rule_one_fair_value") == "ruleOneFairValue"
    assert snake_to_camel("id") == "id"


def test_round_trips_every_savedvaluation_field_name():
    fields = [
        "ticker",
        "id",
        "evaluatedAt",
        "currentPrice",
        "currency",
        "epsTtm",
        "epsOverride",
        "years",
        "growthRatePercent",
        "exitPeMultiple",
        "requiredReturnPercent",
        "mosPercent",
        "ruleOneFairValue",
        "base",
        "bear",
        "bull",
        "notes",
        "evaluator",
    ]
    for field in fields:
        assert snake_to_camel(camel_to_snake(field)) == field


def test_keys_to_snake_case_converts_nested_dicts_and_lists():
    payload = {
        "ticker": "AAPL",
        "growthRatePercent": 10,
        "base": {"exitPeMultiple": 15, "ruleOneFairValue": 180},
        "history": [{"currentPrice": 220}, {"currentPrice": 225}],
    }

    result = keys_to_snake_case(payload)

    assert result == {
        "ticker": "AAPL",
        "growth_rate_percent": 10,
        "base": {"exit_pe_multiple": 15, "rule_one_fair_value": 180},
        "history": [{"current_price": 220}, {"current_price": 225}],
    }


def test_keys_to_camel_case_converts_nested_dicts_and_lists():
    payload = {
        "ticker": "AAPL",
        "growth_rate_percent": 10,
        "base": {"exit_pe_multiple": 15, "rule_one_fair_value": 180},
        "history": [{"current_price": 220}, {"current_price": 225}],
    }

    result = keys_to_camel_case(payload)

    assert result == {
        "ticker": "AAPL",
        "growthRatePercent": 10,
        "base": {"exitPeMultiple": 15, "ruleOneFairValue": 180},
        "history": [{"currentPrice": 220}, {"currentPrice": 225}],
    }


def test_non_dict_non_list_values_pass_through_unchanged():
    assert keys_to_snake_case(None) is None
    assert keys_to_snake_case(42) == 42
    assert keys_to_snake_case("plain string") == "plain string"
