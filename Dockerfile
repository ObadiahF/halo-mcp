FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./HaloMCP/

ENV MCP_TRANSPORT=sse
ENV MCP_HOST=0.0.0.0
EXPOSE 8000

CMD ["python", "-m", "HaloMCP"]
