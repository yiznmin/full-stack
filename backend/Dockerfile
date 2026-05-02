# PaintLearn backend image — FastAPI + Celery + paint-by-number engine + SAM
#
# 兩個 service 共用：
#   - backend-web: bash scripts/start_web.sh
#   - backend-worker: bash scripts/start_worker.sh
#
# 大小：~3GB（torch ~800MB + SAM model ~375MB + libs）

FROM python:3.12-slim

# 系統依賴
#   inkscape: paint-by-number/src/export_pdf.py 用（CLI SVG→PDF）
#   curl: Dockerfile 內下載 SAM model
#   libcairo2 / libpango-1.0-0 / libpangocairo-1.0-0: cairosvg + svglib（PDF 匯出）
#   libgl1 / libglib2.0-0: opencv-python（headless 環境也要 libglib）
RUN apt-get update && apt-get install -y --no-install-recommends \
    inkscape \
    curl \
    git \
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps（先複製 requirements.txt 利用 layer cache）─────────────────
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── SAM vit_b model（375MB）— 獨立 layer，requirements 沒變時不重下────────
RUN mkdir -p /app/models \
 && curl -fL --retry 3 \
    https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth \
    -o /app/models/sam_vit_b.pth

# ── 環境變數（部署時可用 Railway env 覆蓋）─────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SAM_MODEL_PATH=/app/models/sam_vit_b.pth \
    INKSCAPE_PATH=/usr/bin/inkscape

# ── 取 paint-by-number 引擎 source（engine.py 透過 sys.path 載入）─────────
# 不依賴 git submodule fetch（Railway clone 不一定 --recursive），改在 build 階段
# 直接 git clone 釘住的 commit；只取 src/ 子目錄，丟棄 images / models / output 等大資產。
ARG PBN_COMMIT=3e66ecebda1d6a5e6f4bf87e94adb237a19d55bf
RUN git clone https://github.com/yiznmin/PaintingNumber.git /tmp/pbn \
 && cd /tmp/pbn && git checkout ${PBN_COMMIT} \
 && mkdir -p /app/paint-by-number \
 && cp -r /tmp/pbn/src /app/paint-by-number/src \
 && rm -rf /tmp/pbn

# ── 複製 backend 程式碼（最後一層、變更最頻繁，cache 命中率最低）───────────
COPY backend /app

# 把 scripts 設可執行
RUN chmod +x /app/scripts/start_web.sh /app/scripts/start_worker.sh

# Railway 給 PORT env var；start_web.sh 讀
EXPOSE 8000
CMD ["bash", "scripts/start_web.sh"]
