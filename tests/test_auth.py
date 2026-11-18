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


# ----- forgot password -----

class Outbox:
    """stands in for the email sender and keeps what would be sent"""

    def __init__(self):
        self.sent = []

    def __call__(self, email, name, code):
        self.sent.append((email, name, code))


def test_reset_with_emailed_code(store):
    auth.sign_up(store, "Manasa", "manasa@example.com", "oldpass123")
    outbox = Outbox()
    auth.start_reset(store, " Manasa@Example.com ", outbox, now=1000)
    email, name, code = outbox.sent[0]
    assert email == "manasa@example.com" and name == "Manasa"
    assert len(code) == 6 and code.isdigit()
    assert code not in str(store.get_code(email))  # only a hash is saved
    user, token = auth.finish_reset(store, email, code, "newpass123", now=1100)
    assert auth.read_token(token)["email"] == email
    auth.log_in(store, email, "newpass123")
    with pytest.raises(auth.AuthError):
        auth.log_in(store, email, "oldpass123")
    with pytest.raises(auth.AuthError):  # a code works only once
        auth.finish_reset(store, email, code, "another123", now=1200)


def test_unknown_email_sends_nothing_but_looks_the_same(store):
    outbox = Outbox()
    assert auth.start_reset(store, "nobody@example.com", outbox) is None
    assert outbox.sent == []
    with pytest.raises(auth.AuthError):
        auth.start_reset(store, "not-an-email", outbox)


def test_code_expires_and_resend_waits(store):
    auth.sign_up(store, "Sherlyn", "s@example.com", "oldpass123")
    outbox = Outbox()
    auth.start_reset(store, "s@example.com", outbox, now=1000)
    auth.start_reset(store, "s@example.com", outbox, now=1030)  # too soon: no second email
    assert len(outbox.sent) == 1
    code = outbox.sent[0][2]
    with pytest.raises(auth.AuthError) as late:
        auth.finish_reset(store, "s@example.com", code, "newpass123", now=1000 + 16 * 60)
    assert "expired" in late.value.message


def test_too_many_wrong_codes(store):
    auth.sign_up(store, "Sherlyn", "s@example.com", "oldpass123")
    outbox = Outbox()
    auth.start_reset(store, "s@example.com", outbox, now=1000)
    code = outbox.sent[0][2]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(auth.RESET_MAX_TRIES):
        with pytest.raises(auth.AuthError) as error:
            auth.finish_reset(store, "s@example.com", wrong, "newpass123", now=1010)
        assert error.value.message.startswith("Wrong code")
    with pytest.raises(auth.AuthError) as blocked:
        auth.finish_reset(store, "s@example.com", code, "newpass123", now=1020)
    assert blocked.value.status == 429
    auth.log_in(store, "s@example.com", "oldpass123")  # password unchanged


def test_reset_email_text():
    from backend.services.email_sender import reset_email
    subject, text, html = reset_email("Manasa Bomma", "123456")
    assert "123456" in subject and "123456" in text and "123456" in html
    assert text.startswith("Hi Manasa,")
