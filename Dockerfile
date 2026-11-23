# JADEN API server: offline Japanese address normalization over HTTP.
#
#   docker build -t jaden .
#   docker run --rm -p 8000:8000 jaden
#   curl 'http://127.0.0.1:8000/v1/normalize?q=港区芝公園4-2-8'
#
# The image holds everything it needs; it makes no network calls at run time.
# To bake in block-level points for some prefectures (downloaded at build time):
#   docker build --build-arg BLOCKS="13 27" -t jaden .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 XDG_DATA_HOME=/home/jaden/.local/share
WORKDIR /src
COPY pyproject.toml README.md README_JP.md LICENSE NOTICE MANIFEST.in ./
COPY src ./src
RUN pip install --no-cache-dir . && rm -rf /src \
 && useradd --create-home --uid 10001 jaden

USER jaden
WORKDIR /home/jaden
ARG BLOCKS=""
RUN if [ -n "$BLOCKS" ]; then jaden data fetch-blocks $BLOCKS; fi

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status != 200)"
ENTRYPOINT ["jaden"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000", "--quiet"]
