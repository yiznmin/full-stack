"""連到 user 的 chrome（port 9222）— 拉所有商品 + 每個商品的圖片，
找出哪些 image_url 是壞的（HEAD 不回 200）+ 為什麼。

要先確保 chrome 開著、admin 登入過（cookie 存在）。
"""
import json
import urllib.request


PORT = 9222


def fetch_with_cookie(url, cookie_str):
    req = urllib.request.Request(url)
    req.add_header("Cookie", cookie_str)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def head_url(url):
    """Returns (status, headers dict) or (0, error_msg)."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def get_admin_cookie() -> str:
    """讀取 access_token cookie（curl 存的 netscape format）。"""
    import os
    paths = [
        "/tmp/admin-cookie.txt",
        os.path.expandvars(r"%TEMP%\admin-cookie.txt"),
    ]
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path) as f:
        for line in f:
            if "access_token" in line:
                # netscape cookie format: domain TAB ... TAB name TAB value
                parts = line.strip().split("\t")
                if len(parts) >= 7 and parts[5] == "access_token":
                    return f"access_token={parts[6]}"
    return ""


def main():
    cookie = get_admin_cookie()
    if not cookie:
        print("[!] No admin cookie found. Run login first.")
        return
    print(f"Cookie: {cookie[:50]}...")

    BASE = "https://paint-web-production.up.railway.app/api/v1"

    # 1. 拿所有商品
    products = fetch_with_cookie(f"{BASE}/admin/products?page=1&page_size=100", cookie)
    print(f"\n=== Found {products['total']} products ===")

    bad_count = 0
    good_count = 0
    samples = []

    for p in products["items"][:5]:  # 只看前 5 個
        print(f"\n[{p['title']}] id={p['id']}")
        if p.get("cover_image_url"):
            status, _ = head_url(p["cover_image_url"])
            mark = "✓" if status == 200 else "✗"
            print(f"  {mark} cover {status}: {p['cover_image_url'][:100]}")
            if status != 200:
                bad_count += 1
                samples.append({"type": "cover", "url": p["cover_image_url"], "status": status})
            else:
                good_count += 1

        # 拿這個商品的 images
        try:
            detail = fetch_with_cookie(f"{BASE}/admin/products/{p['id']}", cookie)
            images = detail.get("images", [])
            if isinstance(images, dict):
                images = images.get("items", [])
            for img in images:
                status, _ = head_url(img["image_url"])
                mark = "✓" if status == 200 else "✗"
                print(f"  {mark} img {status}: {img['image_url'][:100]}")
                if status != 200:
                    bad_count += 1
                    samples.append({"type": "image", "url": img["image_url"], "status": status})
                else:
                    good_count += 1
        except Exception as e:
            print(f"  ! detail fetch failed: {e}")

    print(f"\n=== Summary ===")
    print(f"Good URLs: {good_count}")
    print(f"Bad URLs: {bad_count}")
    if samples:
        print(f"\nFirst broken sample:")
        for s in samples[:3]:
            print(f"  {s['type']} status={s['status']}: {s['url']}")


if __name__ == "__main__":
    main()
