FROM python@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f AS test
WORKDIR /test
COPY bridge.py test_bridge.py ./
RUN python -m unittest -v test_bridge

FROM python@sha256:05cda9777409a9c3ffddd94a4c476b79f0769a0b4857f0c7ed9226b6800b0d6f
WORKDIR /app
COPY --from=test /test/bridge.py .
RUN mkdir /data && chown 65532:65532 /data
USER 65532:65532
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8084
CMD ["python", "bridge.py"]
