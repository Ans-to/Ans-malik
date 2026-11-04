from pathlib import Path
from forge_python import assemble

def test_every_chunk_is_finished_before_concat(monkeypatch, tmp_path):
    calls = []
    def finish(source, target, seed):
        calls.append((source, seed))
        target.touch()
    def run(command, check):
        assert len(calls) == 2
        manifest = Path(command[command.index('-i') + 1]).read_text()
        assert 'finished-0000.mp4' in manifest and 'finished-0001.mp4' in manifest
    monkeypatch.setattr(assemble, 'finish_video', finish)
    monkeypatch.setattr(assemble.subprocess, 'run', run)
    assemble.assemble(['a.mp4', 'b.mp4'], tmp_path / 'output.mp4')
    assert calls == [('a.mp4', 0), ('b.mp4', 1)]
