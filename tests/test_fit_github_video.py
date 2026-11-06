import subprocess
from pathlib import Path
import pytest
from scripts.fit_github_video import fit

def test_small_file_is_unchanged(tmp_path):
    path=tmp_path/'video.mp4';path.write_bytes(b'unchanged');fit(path,100)
    assert path.read_bytes()==b'unchanged'

def test_failure_does_not_replace_original(tmp_path,monkeypatch):
    path=tmp_path/'video.mp4';path.write_bytes(b'original')
    def failed(*args,**kwargs): raise subprocess.CalledProcessError(1,'ffmpeg')
    monkeypatch.setattr(subprocess,'run',failed)
    with pytest.raises(subprocess.CalledProcessError):fit(path,1)
    assert path.read_bytes()==b'original'
