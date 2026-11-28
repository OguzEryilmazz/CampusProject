FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kampus_mcp ./kampus_mcp

# Yetkisiz kullanıcıyla çalış
RUN useradd --system --uid 10001 --no-create-home app
USER app

ENV MCP_HOST=0.0.0.0 \
    MCP_PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,os,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('MCP_PORT','8080')+'/health',timeout=4).status==200 else 1)"

# Tek süreç: oran sınırı bellekte tutulur, --workers kullanma.
CMD ["python", "-m", "kampus_mcp.server"]
