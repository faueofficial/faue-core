from faue_core.telemetry.scrub import REDACTED, scrub


def test_sensitive_keys_redacted():
    assert scrub({"email": "a@b.com", "user_id": "123"}) == {
        "email": REDACTED, "user_id": "123"}


def test_nested_structures_redacted():
    out = scrub({"user": {"phone": "+2348012345678", "id": "x"}, "items": [{"name": "shirt"}]})
    assert out["user"]["phone"] == REDACTED
    assert out["user"]["id"] == "x"
    assert out["items"][0]["name"] == REDACTED


def test_emails_in_free_text_redacted():
    assert "a@b.com" not in scrub("login failed for a@b.com")


def test_phone_numbers_in_free_text_redacted():
    assert "8012345678" not in scrub("sms to +234 801 234 5678 failed")


def test_safe_values_pass_through():
    assert scrub({"trace_id": "abc", "status": 200}) == {"trace_id": "abc", "status": 200}
