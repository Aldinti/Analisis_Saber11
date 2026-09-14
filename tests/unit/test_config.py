from saber11.config import get_dq_rules, get_hmac_key, get_settings, get_source_contract


def test_load_settings():
    settings = get_settings()
    assert "paths" in settings
    assert "lakehouse" in settings
    assert settings["privacy"]["k_min"] == 5


def test_load_source_contract():
    contract = get_source_contract()
    assert "source_contract" in contract
    assert contract["source_contract"]["expected_columns_count"] == 23


def test_load_dq_rules():
    rules_data = get_dq_rules()
    assert "rules" in rules_data
    assert len(rules_data["rules"]) > 0


def test_get_hmac_key():
    key = get_hmac_key()
    assert len(key) >= 32
