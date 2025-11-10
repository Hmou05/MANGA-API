# ...existing code...
import pytest
from tools import get_extension

def test_basic():
    assert get_extension("https://example.com/a.png") == "png"
    assert get_extension("https://example.com/a.jpg?x=1") == "jpg"
    assert get_extension("https://example.com/dir/") == ""
    assert get_extension("") == ""
    assert get_extension("https://example.com/archive.tar.gz") == "tar.gz"
    assert get_extension("https://example.com/file") == ""
# ...existing code...