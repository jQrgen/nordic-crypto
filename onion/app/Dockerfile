FROM python:3.12-slim-bookworm
RUN useradd --system --uid 65532 --home /app --shell /usr/sbin/nologin tip
WORKDIR /app
COPY server.py copy.json ./
USER root
ENV BIND=0.0.0.0 PORT=8080 QUEUE_DIR=/var/lib/nordic-tips DROP_UID=65532
EXPOSE 8080
CMD ["python3", "-u", "server.py"]
