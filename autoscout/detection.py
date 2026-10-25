"""Shared pretrained detector configuration."""
import numpy as np

def proposal_limit(model, imgsz=960):
    """Keep every spatial proposal, including end-to-end head postprocessing."""
    head = getattr(getattr(model, 'model', None), 'model', [None])[-1]
    strides = getattr(head, 'stride', None)
    values = strides.tolist() if strides is not None else [8, 16, 32]
    limit = sum(int(np.ceil(imgsz / stride)) ** 2 for stride in values if stride > 0)
    if head is not None:
        head.max_det = limit
    return limit

