from types import SimpleNamespace
import numpy as np
from autoscout.detection import proposal_limit


def test_removes_head_and_prediction_truncation_at_300():
    head=SimpleNamespace(stride=np.array([8,16,32]),max_det=300)
    model=SimpleNamespace(model=SimpleNamespace(model=[head]))
    assert proposal_limit(model)==120**2+60**2+30**2
    assert head.max_det==18900
