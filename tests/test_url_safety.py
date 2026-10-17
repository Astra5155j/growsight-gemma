import pytest
from backend.main import validate_public_url


@pytest.mark.parametrize("url", [
    "http://localhost",
    "http://127.0.0.1",
    "http://192.168.1.1",
    "http://10.0.0.1",
    "file:///etc/passwd",
    "ftp://example.com",
])
def test_private_or_unsupported_urls_rejected(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_public_url_normalizes_fragment():
    assert validate_public_url("https://example.com#hello") == "https://example.com"
