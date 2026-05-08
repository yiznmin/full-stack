// Upload helper — 客製照片上傳
// Flow: POST /upload/custom-photo → 拿 signed URL → PUT 直傳 Firebase
// 回 firebase_path（私密路徑），存到 custom_request.photo_url；admin 端會用
// /admin/custom-requests/{id}/photo-signed-url 取讀取簽名。

const API_BASE = '/api/v1'

interface PrivateSignedUrl {
  upload_url: string
  firebase_path: string
  expires_at: string
}

async function getCustomPhotoSignedUrl(
  filename: string,
  content_type: 'image/jpeg' | 'image/png',
  size: number,
): Promise<PrivateSignedUrl> {
  const res = await fetch(`${API_BASE}/upload/custom-photo`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content_type, size }),
  })
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => b?.detail?.message ?? b?.detail ?? `${res.status}`)
      .catch(() => `${res.status}`)
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return (await res.json()) as PrivateSignedUrl
}

/** Returns firebase_path (private). 不是公開 URL。 */
export async function uploadCustomPhoto(file: File): Promise<string> {
  const contentType: 'image/png' | 'image/jpeg' =
    file.type === 'image/png' ? 'image/png' : 'image/jpeg'

  const signed = await getCustomPhotoSignedUrl(file.name, contentType, file.size)

  let putRes: Response
  try {
    putRes = await fetch(signed.upload_url, {
      method: 'PUT',
      headers: { 'Content-Type': contentType },
      body: file,
    })
  } catch (e) {
    throw new Error(
      'PUT Firebase 失敗（可能是 CORS）。原始錯誤：' + (e as Error).message,
    )
  }

  if (!putRes.ok && !signed.upload_url.startsWith('https://stub.firebase')) {
    throw new Error(`Firebase 拒絕上傳：HTTP ${putRes.status}`)
  }

  return signed.firebase_path
}
