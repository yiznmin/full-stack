"""SAM e2e 測試腳本 — Test 5 驗收用。

跑完整 SAM 流程驗證 Railway 部署：
  1. admin 登入
  2. 上傳一張圖 → Firebase（signed URL 直傳）
  3. /admin/images 註冊圖片 → 拿 image_id
  4. /admin/production/jobs 建一個 sam_refine job → 拿 job_id + batch_id
  5. /admin/production/jobs/{id}/sam-mask 用 sam_points（中心一點 fg）
     → paint-web 跑 SAM ViT-B 推論（30-60s）→ 產 mask → 上傳 Firebase
  6. /admin/production/batches/{id}/start → Celery 觸發 worker
  7. paint-worker 跑 sam_refine pipeline（pbn 引擎用 mask 細化）→ 上傳 SVG/filled
  8. 輪詢 GET /admin/production/jobs/{id} 直到 status=completed/failed

使用：
    cd backend
    venv/Scripts/python scripts/test_sam_e2e.py \\
        --base-url https://paint-web-production.up.railway.app \\
        --email yizn.min@gmail.com \\
        --password aa0965721667 \\
        --image path/to/test.jpg

要求：requests、Pillow（讀圖片寬高）— backend venv 已有。
"""
import argparse
import sys
import time
from pathlib import Path

import requests
from PIL import Image


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="例 https://paint-web-production.up.railway.app")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--image", required=True, help="本地圖片路徑（jpg/png）")
    parser.add_argument("--mode", default="sam_refine", choices=["sam_refine", "sam_weighted"])
    parser.add_argument("--canvas-w-cm", type=float, default=30.0)
    parser.add_argument("--canvas-h-cm", type=float, default=40.0)
    parser.add_argument("--detail", default="standard", choices=["rough", "standard", "detailed", "premium"])
    parser.add_argument("--difficulty", default="intermediate",
                        choices=["beginner", "elementary", "intermediate", "advanced"])
    parser.add_argument("--extra-colors", type=int, default=3, help="sam_refine 必填，>0")
    parser.add_argument("--weight-ratio", type=float, default=0.65, help="sam_weighted 用，0.5-0.8")
    parser.add_argument("--poll-interval", type=int, default=10, help="輪詢秒數")
    parser.add_argument("--timeout", type=int, default=600, help="總等待秒數上限（10min）")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[ERR] 圖片不存在：{image_path}")
        return 1

    base = args.base_url.rstrip("/") + "/api/v1"
    sess = requests.Session()
    sess.headers["Content-Type"] = "application/json"

    # ── 1. 登入 ───────────────────────────────────────────────────────────────
    print(f"[1] 登入 {args.email} ...")
    r = sess.post(f"{base}/admin/auth/login",
                  json={"email": args.email, "password": args.password})
    r.raise_for_status()
    print(f"    OK，cookie={list(sess.cookies.keys())}")

    # ── 2. 上傳圖片到 Firebase（簽名 URL 直傳）────────────────────────────────
    print(f"[2] 取上傳簽名 URL ...")
    img = Image.open(image_path)
    img_w, img_h = img.size
    content_type = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    file_size = image_path.stat().st_size

    r = sess.post(f"{base}/upload/production-image",
                  json={"filename": image_path.name,
                        "content_type": content_type,
                        "size": file_size})
    r.raise_for_status()
    upload_data = r.json()
    upload_url = upload_data["upload_url"]
    # 後端 /admin/images.original_url 接受 public_url（15-min signed read URL，後端會轉 gs://）
    final_url = upload_data["public_url"]
    print(f"    upload_url 拿到（前 80 字元）：{upload_url[:80]}...")
    print(f"    final URL: {final_url}")

    print(f"[2b] PUT 圖片到 Firebase（{file_size:,} bytes）...")
    with open(image_path, "rb") as f:
        r = requests.put(upload_url, data=f.read(), headers={"Content-Type": content_type})
    r.raise_for_status()
    print(f"    OK")

    # ── 3. 註冊圖片到 DB ─────────────────────────────────────────────────────
    print(f"[3] 註冊圖片 {img_w}×{img_h} ...")
    r = sess.post(f"{base}/admin/images",
                  json={"original_url": final_url,
                        "filename": image_path.name,
                        "width": img_w, "height": img_h})
    r.raise_for_status()
    image_id = r.json()["id"]
    print(f"    image_id={image_id}")

    # ── 4. 建 sam_refine job ─────────────────────────────────────────────────
    print(f"[4] 建 {args.mode} job ...")
    job_params = {
        "detail": args.detail,
        "difficulty": args.difficulty,
        "mode": args.mode,
        "canvas_w_cm": args.canvas_w_cm,
        "canvas_h_cm": args.canvas_h_cm,
    }
    if args.mode == "sam_refine":
        job_params["extra_colors"] = args.extra_colors
    else:  # sam_weighted
        job_params["weight_ratio"] = args.weight_ratio

    r = sess.post(f"{base}/admin/production/jobs",
                  json={"image_id": image_id, "jobs": [job_params]})
    r.raise_for_status()
    create_resp = r.json()
    batch_id = create_resp["batch_id"]
    job_id = create_resp["job_ids"][0]
    print(f"    batch_id={batch_id}")
    print(f"    job_id={job_id}")

    # ── 5. 設 SAM mask（sam_points：圖片中心一點 foreground）─────────────────
    cx, cy = img_w // 2, img_h // 2
    print(f"[5] 觸發 SAM 推論（前景點 ({cx}, {cy})）— paint-web 將載入 ViT-B 模型，預計 30-60s ...")
    t0 = time.time()
    r = sess.post(f"{base}/admin/production/jobs/{job_id}/sam-mask",
                  json={"sam_points": [{"x": cx, "y": cy, "label": 1}],
                        "mode": args.mode})
    sam_elapsed = time.time() - t0
    if r.status_code >= 400:
        print(f"    [ERR] SAM mask 失敗 status={r.status_code}: {r.text}")
        return 1
    mask_resp = r.json()
    print(f"    OK ({sam_elapsed:.1f}s)，coverage={mask_resp.get('mask_coverage')}")
    print(f"    mask_url={mask_resp.get('mask_url', '(none)')}")

    # ── 6. 啟動 batch（送進 Celery）──────────────────────────────────────────
    print(f"[6] 啟動 batch {batch_id} → 進 Celery 佇列 ...")
    r = sess.post(f"{base}/admin/production/batches/{batch_id}/start")
    r.raise_for_status()
    print(f"    OK，{r.json()}")

    # ── 7. 輪詢 job 狀態 ─────────────────────────────────────────────────────
    print(f"[7] 輪詢 job 狀態（每 {args.poll_interval}s，最多 {args.timeout}s）...")
    deadline = time.time() + args.timeout
    last_status = None
    while time.time() < deadline:
        r = sess.get(f"{base}/admin/production/jobs/{job_id}")
        r.raise_for_status()
        job = r.json()
        status = job["status"]
        if status != last_status:
            elapsed = int(time.time() - (deadline - args.timeout))
            print(f"    [{elapsed:3d}s] status={status}")
            last_status = status
        if status == "completed":
            print(f"\n[OK] SAM e2e 完成！")
            print(f"    svg_url             = {job.get('svg_url')}")
            print(f"    filled_template_url = {job.get('filled_template_url')}")
            print(f"    snapped_rgb_url     = {job.get('snapped_rgb_url')}")
            print(f"    num_colors_used     = {job.get('num_colors_used')}")
            return 0
        if status == "failed":
            print(f"\n[FAIL] job 失敗：{job.get('error_message')}")
            return 2
        time.sleep(args.poll_interval)

    print(f"\n[TIMEOUT] {args.timeout}s 內未完成，最後 status={last_status}")
    return 3


if __name__ == "__main__":
    sys.exit(main())
