############## build stage ##############
FROM python:3.10-slim AS builder
WORKDIR /app

# 建一個獨立的 venv 裝依賴
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

############## runtime stage ############
FROM python:3.10-slim

# 非 root 使用者
RUN adduser --disabled-password --gecos '' appuser
USER appuser
WORKDIR /app

# 複製虛擬環境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "4", \
     "-b", "0.0.0.0:8000", "app.main:app"]
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]