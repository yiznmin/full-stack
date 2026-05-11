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
    libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python deps（先複製 requirements.txt 利用 layer cache）─────────────────
# 先單獨從 PyTorch 官方 CPU wheel index 安裝 torch / torchvision（避免 Railway → PyPI 慢/抖動），
# 再從 PyPI 安裝其餘 deps（torch 已裝，pip 不會重下）。
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cpu \
      torch==2.4.1 torchvision==0.19.1 \
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
# 不依賴 git submodule fetch（Railway clone 不一定 --recursive）；
# 不用 git clone（Docker non-interactive 環境 git 對 GitHub 觸發 auth prompt 失敗）；
# 改用 curl 抓 GitHub codeload tarball（純 HTTP，匿名可讀，無 auth 問題）。
# commit hash 直接寫死於 RUN 內，避免 Docker ARG 展開不可預期的問題。
RUN curl -fL "https://codeload.github.com/yiznmin/PaintingNumber/tar.gz/6d96f1de28d71e8bb1c1cb6c89936df7d684d941" \
        -o /tmp/pbn.tar.gz \
 && mkdir -p /tmp/pbn /app/paint-by-number \
 && tar -xzf /tmp/pbn.tar.gz -C /tmp/pbn --strip-components=1 \
 && cp -r /tmp/pbn/src /app/paint-by-number/src \
 && rm -rf /tmp/pbn /tmp/pbn.tar.gz

# ── 複製 backend 程式碼（最後一層、變更最頻繁，cache 命中率最低）───────────
COPY backend /app

# 把 scripts 設可執行
RUN chmod +x /app/scripts/start.sh /app/scripts/start_web.sh /app/scripts/start_worker.sh

# Railway 給 PORT env var；start_web.sh 讀
EXPOSE 8000

# 容器入口統一走 start.sh dispatcher，依 SERVICE_TYPE env var 分流：
#   SERVICE_TYPE=web    (預設) → start_web.sh
#   SERVICE_TYPE=worker        → start_worker.sh
# 各 Railway service 在 Variables 設自己的 SERVICE_TYPE。
CMD ["bash", "scripts/start.sh"]
