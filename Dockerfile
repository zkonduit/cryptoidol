# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.9.6-slim
WORKDIR /code
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
RUN apt-get update
RUN apt-get install -y gcc g++ cmake make gfortran pkg-config libffi-dev git curl ffmpeg libavcodec-extra libssl-dev
RUN git clone https://github.com/zkonduit/pyezkl
RUN curl -sSL https://install.python-poetry.org | python3 -;
ENV PATH="/root/.local/bin:$PATH"
# Copy only requirements to cache them in docker layer
WORKDIR /code
COPY poetry.lock pyproject.toml /code/
# Project initialization:
RUN poetry install
#  we do this to get a more recent ezkl_lib
RUN git clone https://github.com/zkonduit/ezkl
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN rustup override set nightly
RUN poetry run maturin develop --release --features python-bindings --target-dir ezkl --manifest-path ezkl/Cargo.toml
EXPOSE 5000
CMD ["poetry", "run", "flask", "run"]
