FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ARG REF=main
USER root
RUN apt-get update && apt-get install -y libsndfile1-dev espeak-ng time git libgl1-mesa-glx libgl1 g++ tesseract-ocr
ENV UV_PYTHON=/usr/local/bin/python
RUN pip --no-cache-dir install uv &&  uv venv && uv pip install --no-cache-dir -U pip setuptools
RUN pip install --no-cache-dir 'torch' 'torchvision' 'torchaudio' --index-url https://download.pytorch.org/whl/cpu
RUN uv pip install --no-cache-dir  --no-deps timm accelerate
RUN pip install -U --upgrade-strategy eager --no-cache-dir pytesseract python-Levenshtein opencv-python nltk
RUN pip install  --no-cache-dir "git+https://github.com/huggingface/transformers.git@#egg=transformers[testing, vision]" 'scikit-learn' 'torch-stft' 'nose'  'dataset'
RUN pip install 'git+https://github.com/facebookresearch/detectron2.git@92ae9f0b92aba5867824b4f12aa06a22a60a45d3'
RUN pip uninstall -y transformers
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
