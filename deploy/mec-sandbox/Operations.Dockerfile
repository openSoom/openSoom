FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
WORKDIR /opt/opensoom
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src ./src
COPY config ./config
COPY profiles ./profiles
COPY schemas ./schemas
COPY scenarios ./scenarios
COPY web ./web
ENV PYTHONPATH=/opt/opensoom/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
ENTRYPOINT ["python","-m","uvicorn"]
