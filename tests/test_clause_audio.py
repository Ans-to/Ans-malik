import numpy as np
import soundfile as sf
from clause_audio import concatenate


def test_exact_sample_windows_and_180ms_gaps(tmp_path):
    sr = 48000
    originals = [np.arange(n, dtype=np.int16)+i*100 for i, n in enumerate([1001, 2403, 3907, 4111, 5003, 6199])]
    paths = []
    for i, data in enumerate(originals):
        p = tmp_path / f'{i}.wav'
        sf.write(p, data, sr, subtype='PCM_16')
        paths.append(p)
    out = tmp_path / 'all.wav'
    meta = concatenate(paths, out)
    actual, rate = sf.read(out, dtype='int16')
    assert rate == sr
    assert meta['lead_samples'] == 8640 and meta['gap_samples'] == 8640
    assert len(actual) == meta['total_samples']
    for i, (clause, expected) in enumerate(zip(meta['clauses'], originals)):
        a, b = clause['start_sample'], clause['end_sample']
        assert b-a == len(expected)
        assert clause['start_sec'] == a/sr and clause['end_sec'] == b/sr
        np.testing.assert_array_equal(actual[a:b], expected)
        if i:
            prev = meta['clauses'][i-1]['end_sample']
            assert a-prev == 8640 and not actual[prev:a].any()
