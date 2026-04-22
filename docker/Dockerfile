# baha 爬蟲 app container 定義。
#
# 使用 python:3.12-slim 為 base image；先複製 requirements.txt 並安裝依賴，
# 再複製原始碼以利 Docker layer 快取。PYTHONPATH 設為 /app/src 讓
# `python -m baha` 能在 /app 工作目錄下直接匯入套件。
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TZ=Asia/Taipei

WORKDIR /app

# 安裝系統層最小必要套件（tzdata 供 ZoneInfo 使用、build tools 於 wheel 已足時不需要）。
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/
COPY tests/ /app/tests/

# 預設指令：執行一次抓取。
CMD ["python", "-m", "baha"]
