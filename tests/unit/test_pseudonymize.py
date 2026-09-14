import pytest

from saber11.security.pseudonymize import pseudonymize_id


def test_pseudonymize_id_determinism():
    key = "secret_key_1234567890123456789012"
    doc = 1012345678
    pid1 = pseudonymize_id(key, doc)
    pid2 = pseudonymize_id(key, doc)
    assert pid1 == pid2
    assert len(pid1) == 64


def test_pseudonymize_id_different_keys():
    doc = 1012345678
    pid1 = pseudonymize_id("key_one_1234567890123456789012345", doc)
    pid2 = pseudonymize_id("key_two_1234567890123456789012345", doc)
    assert pid1 != pid2


def test_pseudonymize_id_empty_key_or_doc():
    with pytest.raises(ValueError):
        pseudonymize_id("", 123)

    with pytest.raises(ValueError):
        pseudonymize_id("valid_key_12345678901234567890", "")
