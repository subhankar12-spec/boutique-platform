FROM python@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f AS dependencies
WORKDIR /test
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --require-hashes --target=/opt/python -r requirements.txt
ENV PYTHONPATH=/opt/python PYTHONDONTWRITEBYTECODE=1
COPY bridge.py ./

FROM dependencies AS test
COPY test_bridge.py test_postgres.py ./
COPY ci ./ci
RUN chmod -R a+rX /test /opt/python
CMD ["sh", "ci/test.sh"]

FROM python@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
WORKDIR /app
COPY --from=dependencies /opt/python /opt/python
COPY --from=dependencies --chmod=644 /test/bridge.py .
RUN mkdir /data && chown 65532:65532 /data
USER 65532:65532
ENV PYTHONPATH=/opt/python PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8084
CMD ["python", "bridge.py"]
