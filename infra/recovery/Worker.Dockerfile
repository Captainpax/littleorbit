# Controlled build candidate, never a normal Compose dependency/build target.
# RECOVERY_BASE must be the reviewed digest-bound base; no default/tag fallback.
ARG RECOVERY_BASE
FROM ${RECOVERY_BASE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY infra/scripts/array_worker_closure.py /closure/array_worker_closure.py
# These inputs must be separately sealed and supplied; no checked-in fake lock.
COPY infra/recovery/worker-closure.json /closure/worker-closure.json
COPY infra/recovery/wheelhouse/ /wheelhouse/
ARG RECOVERY_BASE
RUN --network=none python /closure/array_worker_closure.py \
      --manifest /closure/worker-closure.json --wheel-root /wheelhouse \
      --expected-base "${RECOVERY_BASE}" --check-runtime > /closure/requirements.lock \
    && python -m pip install --no-index --only-binary=:all: --no-deps \
      --require-hashes --find-links=/wheelhouse -r /closure/requirements.lock \
    && python -m pip check
USER 65532:65532
ENTRYPOINT []
CMD ["python", "-m", "little_orbit_api.worker"]
