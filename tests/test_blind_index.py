import pytest

from faue_core.crypto.blind_index import blind_index, normalise, verify

PEPPER = b"test-pepper-not-for-production"


@pytest.mark.parametrize("variant", [
    "Foo@Bar.com", " foo@bar.com ", "FOO@BAR.COM", "foo@bar.com\t",
])
def test_normalisation_makes_lookups_survive_user_typing(variant):
    """Getting this wrong makes login silently fail for the user who typed a
    trailing space."""
    assert blind_index(variant, PEPPER) == blind_index("foo@bar.com", PEPPER)


def test_different_values_differ():
    assert blind_index("a@b.com", PEPPER) != blind_index("c@d.com", PEPPER)


def test_different_peppers_differ():
    assert blind_index("a@b.com", PEPPER) != blind_index("a@b.com", b"other-pepper")


def test_verify_is_constant_time_and_correct():
    index = blind_index("a@b.com", PEPPER)
    assert verify("A@B.com", index, PEPPER)
    assert not verify("c@d.com", index, PEPPER)


def test_empty_pepper_rejected():
    with pytest.raises(ValueError):
        blind_index("a@b.com", b"")


def test_index_is_hex_sha256():
    index = blind_index("a@b.com", PEPPER)
    assert len(index) == 64 and int(index, 16) >= 0
