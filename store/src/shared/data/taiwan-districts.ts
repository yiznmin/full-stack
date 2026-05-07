// Taiwan counties + districts wrapper
// Source: twzipcode-data (中華郵政 103/12 郵遞區號表)
//
// 直接 import 內部 zh-tw 資料以避開 accept-language locale 依賴
// (twzipcode-data 主入口會 require accept-language，瀏覽器端用不到)

// @ts-expect-error - CJS module without types
import countiesRaw from 'twzipcode-data/dist/zh-tw/counties.js'
// @ts-expect-error - CJS module without types
import zipcodesRaw from 'twzipcode-data/dist/zh-tw/zipcodes.js'

interface RawCounty {
  id: string
  name: string
}
interface RawZipcode {
  id: string
  zipcode: number
  county: string
  city: string  // 行政區名稱（不是縣市，套件命名歷史包袱）
}

const counties = countiesRaw as RawCounty[]
const zipcodes = zipcodesRaw as RawZipcode[]

// 縣市清單
export const TW_COUNTIES: string[] = counties.map((c) => c.name)

// county -> districts map
const districtMap = new Map<string, string[]>()
for (const z of zipcodes) {
  const list = districtMap.get(z.county) ?? []
  if (!list.includes(z.city)) list.push(z.city)
  districtMap.set(z.county, list)
}

export function getDistricts(county: string): string[] {
  return districtMap.get(county) ?? []
}

// 套件用「臺」，但使用者輸入習慣可能是「台」 — 雙向相容查詢
export function normalizeCounty(input: string): string {
  if (!input) return ''
  if (TW_COUNTIES.includes(input)) return input
  // 台 → 臺
  const t = input.replace(/^台/, '臺')
  if (TW_COUNTIES.includes(t)) return t
  // 臺 → 台
  const n = input.replace(/^臺/, '台')
  if (TW_COUNTIES.includes(n)) return n
  return input
}
