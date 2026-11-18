FROM python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df
WORKDIR /opt/opensoom
COPY apps/mec-maintenance/requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --no-deps --requirement /tmp/requirements.lock
COPY src/opensoom/__init__.py src/opensoom/onem2m.py src/opensoom/mec_sensor.py src/opensoom/maintenance_worker.py ./opensoom/
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["python","-m","opensoom.maintenance_worker"]
