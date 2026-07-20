from utils.security import hash_password, password_needs_rehash, verify_password


def test_password_hash_is_salted_and_verifiable():
    first = hash_password("correct horse battery staple", iterations=100_000)
    second = hash_password("correct horse battery staple", iterations=100_000)
    assert first != second
    assert "correct horse" not in first
    assert verify_password("correct horse battery staple", first)
    assert not verify_password("wrong password", first)


def test_malformed_hash_fails_closed():
    assert verify_password("password", "not-a-valid-hash") is False
    assert password_needs_rehash("not-a-valid-hash") is True
