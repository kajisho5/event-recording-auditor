# Event Recording Auditor -- runs fully locally, no network calls (see
# README.md "Requirements"). This image just packages the CLI with ffmpeg
# preinstalled so nothing else needs to be set up on the host.
#
#   docker run --rm -v "$PWD":/data erauditor analyze /data/recording.mp4 --out-dir /data/audit-output

FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .

WORKDIR /data
ENTRYPOINT ["event-recording-auditor"]
CMD ["--help"]
