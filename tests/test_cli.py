import sys
import types

import pytest

from video_gen import cli, save_output


class FakeFile:
    def read(self):
        return b"fake-mp4"


@pytest.fixture
def fake_replicate(monkeypatch):
    calls = []
    mod = types.SimpleNamespace(run=lambda model, input: calls.append((model, input)) or FakeFile())
    monkeypatch.setitem(sys.modules, "replicate", mod)
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test")
    return calls


def test_generates_and_saves(tmp_path, fake_replicate):
    out = tmp_path / "v.mp4"
    rc = cli.main(["a cat surfing", "-o", str(out), "-m", "owner/model", "--input", "duration=5", "--input", "mode=fast"])
    assert rc == 0
    assert out.read_bytes() == b"fake-mp4"
    assert fake_replicate == [("owner/model", {"prompt": "a cat surfing", "duration": 5, "mode": "fast"})]


def test_image_url_passthrough(tmp_path, fake_replicate):
    rc = cli.main(["x", "-o", str(tmp_path / "v.mp4"), "-i", "https://example.com/a.png", "--image-param", "image"])
    assert rc == 0
    assert fake_replicate[0][1]["image"] == "https://example.com/a.png"


def test_list_output(tmp_path):
    out = save_output([FakeFile()], tmp_path / "v.mp4")
    assert out.read_bytes() == b"fake-mp4"


def test_missing_token(tmp_path, monkeypatch, fake_replicate, capsys):
    monkeypatch.delenv("REPLICATE_API_TOKEN")
    assert cli.main(["x", "-o", str(tmp_path / "v.mp4")]) == 1
    assert "REPLICATE_API_TOKEN" in capsys.readouterr().err
