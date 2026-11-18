"""Checks sign-up, log-in, password hashing and login tokens."""

import pytest

from backend.services import auth


@pytest.fixture
def store(tmp_path):
    # a fresh SQLite file for each test, so tests never touch real accounts
    return auth.UserStore("sqlite:///" + str(tmp_path / "users.db"))


def test_password_is_hashed_not_stored():
    stored = auth.hash_password("secret123")
    assert "secret123" not in stored
    assert auth.verify_password("secret123", stored)
    assert not auth.verify_password("secret124", stored)


def test_same_password_gets_a_different_hash_each_time():
    # a random salt per user: two people with the same password look different
    assert auth.hash_password("secret123") != auth.hash_password("secret123")


def test_sign_up_then_log_in(store):
    user, token = auth.sign_up(store, "Sherlyn", " Sherlyn@Example.com ", "secret123")
    assert user["email"] == "sherlyn@example.com"
    assert auth.read_token(token)["name"] == "Sherlyn"
    again, _ = auth.log_in(store, "SHERLYN@example.com", "secret123")
    assert again == user


def test_wrong_password_and_unknown_email_get_the_same_message(store):
    auth.sign_up(store, "Manasa", "manasa@example.com", "secret123")
    with pytest.raises(auth.AuthError) as wrong:
        auth.log_in(store, "manasa@example.com", "nope12345")
    with pytest.raises(auth.AuthError) as unknown:
        auth.log_in(store, "nobody@example.com", "secret123")
    assert wrong.value.message == unknown.value.message
    assert wrong.value.status == 401


def test_sign_up_checks(store):
    for name, email, password in [("", "a@b.com", "secret123"), ("A", "not-an-email", "secret123"),
                                  ("A", "a@b.com", "short")]:
        with pytest.raises(auth.AuthError):
            auth.sign_up(store, name, email, password)
    auth.sign_up(store, "A", "a@b.com", "secret123")
    with pytest.raises(auth.AuthError) as taken:
        auth.sign_up(store, "B", "A@B.com", "secret456")
    assert taken.value.status == 409


def test_token_cannot_be_changed_or_used_after_it_expires():
    token = auth.make_token({"id": 1, "name": "Sherlyn", "email": "s@example.com"}, now=1_000_000)
    assert auth.read_token(token, now=1_000_100)["id"] == "1"
    assert auth.read_token(token, now=1_000_000 + 8 * 86400) is None
    header, payload, signature = token.split(".")
    forged = auth._b64(b'{"sub":"2","name":"X","email":"x@x.com","iat":0,"exp":9999999999}')
    assert auth.read_token(header + "." + forged + "." + signature) is None
    assert auth.read_token("not a token") is None


def test_bearer_header():
    token = auth.make_token({"id": 7, "name": "M", "email": "m@example.com"})
    assert auth.user_from_header("Bearer " + token)["id"] == "7"
    assert auth.user_from_header(token) is None
    assert auth.user_from_header(None) is None
