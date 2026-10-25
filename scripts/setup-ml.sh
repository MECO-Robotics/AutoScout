#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# CUDA 12.6 wheels retain Pascal support; newer CUDA wheel lines may not.
.venv/bin/pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu126
.venv/bin/pip install --no-cache-dir -c scripts/ml-constraints.txt 'ultralytics==8.4.146' 'rapidocr==3.9.2' 'onnxruntime==1.29.0' 'scipy>=1.17,<2'
.venv/bin/python scripts/fetch-model.py
