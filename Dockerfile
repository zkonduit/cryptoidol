# syntax=docker/dockerfile:1
FROM --platform=linux/amd64 python:3.9.6-slim
ENV PYTHONUNBUFFERED=1

WORKDIR /code
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
RUN apt-get update
RUN apt-get install -y gcc g++ cmake make gfortran pkg-config libffi-dev git curl ffmpeg libavcodec-extra libssl-dev
RUN curl -sSL https://install.python-poetry.org | python3 -;
ENV PATH="/root/.local/bin:$PATH"
# Copy only requirements to cache them in docker layer
WORKDIR /code
COPY poetry.lock pyproject.toml /code/
# Project initialization:
RUN poetry install
RUN poetry add gunicorn
EXPOSE 5000
CMD ["poetry", "run", "flask", "run"]
