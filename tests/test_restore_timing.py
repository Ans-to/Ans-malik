import pytest
from restore_timing import compile_times

def test_cues_use_aligned_words_not_number_token_ratios():
    clauses=[{'end_sec':v} for v in [2,5,8,12,15.5,19.1]]
    meta={'clauses':clauses,'frames':1146}
    words=[{'clause_id':i,'word':word,'start_ms':ms} for i,word,ms in [(1,'States',2500),(2,'gold',6000),(3,'digital',9200),(4,'currency',13100),(5,'88%',16500)]]
    c,t=compile_times(meta,words)
    assert c['gold']==pytest.approx(6.1) and c['digital']==pytest.approx(9.3) and c['stat']==pytest.approx(16.6)
    assert t[2]-.25==pytest.approx(c['gold']) and t[3]-.2==pytest.approx(c['currency'])
    assert t[5]==c['stat']
    with pytest.raises(ValueError):compile_times(meta,words[:-1])
