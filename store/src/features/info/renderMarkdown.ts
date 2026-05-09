// 簡易 markdown → HTML（純前端、無依賴）。
// 支援：# / ## / ### 標題、**粗體**、*斜體*、[文字](url)、無序列表、表格、有序列表、blockquote、段落
//
// 為什麼自寫：避免 markdown-it / marked 200KB bundle 開銷；資訊頁內容由 admin 後台
// 寫，scope 受控（不接受任意外部 markdown）。

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function inlineLine(raw: string): string {
  // 用 token 切分：先抓所有 inline pattern 位置
  // 簡化：直接對 raw 跑 applyInline；applyInline 內部已 escape link/code/bold/em 內容；
  // 剩下的純文字也要 escape 才不會被當作 HTML。
  // 作法：先 escape 整行，再把已 escape 的 [..](..)/`..`/**..**/*..* 還原回 markdown 並重做。
  // 實作上更簡單：手動切分。
  const tokens: string[] = []
  let i = 0
  while (i < raw.length) {
    // code
    if (raw[i] === '`') {
      const end = raw.indexOf('`', i + 1)
      if (end > i) {
        tokens.push(`<code>${escapeHtml(raw.slice(i + 1, end))}</code>`)
        i = end + 1
        continue
      }
    }
    // link [text](url)
    if (raw[i] === '[') {
      const close = raw.indexOf(']', i + 1)
      if (close > i && raw[close + 1] === '(') {
        const urlEnd = raw.indexOf(')', close + 2)
        if (urlEnd > close) {
          const text = raw.slice(i + 1, close)
          const url = raw.slice(close + 2, urlEnd)
          tokens.push(
            `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)}</a>`,
          )
          i = urlEnd + 1
          continue
        }
      }
    }
    // bold **text**
    if (raw[i] === '*' && raw[i + 1] === '*') {
      const end = raw.indexOf('**', i + 2)
      if (end > i + 1) {
        tokens.push(`<strong>${escapeHtml(raw.slice(i + 2, end))}</strong>`)
        i = end + 2
        continue
      }
    }
    // italic *text*
    if (raw[i] === '*') {
      const end = raw.indexOf('*', i + 1)
      if (end > i) {
        tokens.push(`<em>${escapeHtml(raw.slice(i + 1, end))}</em>`)
        i = end + 1
        continue
      }
    }
    // 純字元
    tokens.push(escapeHtml(raw[i]))
    i++
  }
  return tokens.join('')
}

export function renderMarkdown(md: string): string {
  if (!md) return ''
  const lines = md.replace(/\r\n/g, '\n').split('\n')

  const out: string[] = []
  let listType: 'ul' | 'ol' | null = null
  let listItems: string[] = []
  let tableHeaders: string[] | null = null
  let tableRows: string[][] = []
  let paragraph: string[] = []
  let inBlockquote = false
  let blockquoteLines: string[] = []

  const flushList = () => {
    if (listType && listItems.length) {
      out.push(`<${listType}>`)
      for (const li of listItems) out.push(`<li>${li}</li>`)
      out.push(`</${listType}>`)
    }
    listType = null
    listItems = []
  }

  const flushTable = () => {
    if (tableHeaders) {
      out.push('<div class="md-table-wrap"><table class="md-table">')
      out.push('<thead><tr>')
      for (const h of tableHeaders) out.push(`<th>${inlineLine(h)}</th>`)
      out.push('</tr></thead>')
      if (tableRows.length) {
        out.push('<tbody>')
        for (const row of tableRows) {
          out.push('<tr>')
          for (const cell of row) out.push(`<td>${inlineLine(cell)}</td>`)
          out.push('</tr>')
        }
        out.push('</tbody>')
      }
      out.push('</table></div>')
    }
    tableHeaders = null
    tableRows = []
  }

  const flushParagraph = () => {
    if (paragraph.length) {
      const text = paragraph.map(inlineLine).join(' ')
      out.push(`<p>${text}</p>`)
      paragraph = []
    }
  }

  const flushBlockquote = () => {
    if (blockquoteLines.length) {
      out.push('<blockquote>')
      for (const l of blockquoteLines) out.push(`<p>${inlineLine(l)}</p>`)
      out.push('</blockquote>')
      blockquoteLines = []
    }
    inBlockquote = false
  }

  const flushAll = () => {
    flushParagraph()
    flushList()
    flushTable()
    flushBlockquote()
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trim()

    // 空行 = 段落分隔
    if (!trimmed) {
      flushAll()
      continue
    }

    // 標題
    const h = /^(#{1,3})\s+(.+)$/.exec(trimmed)
    if (h) {
      flushAll()
      const level = h[1].length
      out.push(`<h${level}>${inlineLine(h[2])}</h${level}>`)
      continue
    }

    // 表格：第一行 |...| 第二行 |---|
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const cells = trimmed.slice(1, -1).split('|').map((s) => s.trim())
      const next = (lines[i + 1] || '').trim()
      const isSeparator = /^\|[-:\s|]+\|$/.test(next)

      if (!tableHeaders && isSeparator) {
        flushParagraph()
        flushList()
        flushBlockquote()
        tableHeaders = cells
        i++ // 跳過分隔行
        continue
      }
      if (tableHeaders) {
        tableRows.push(cells)
        continue
      }
      // 沒有 separator 的單獨 |..| 當段落處理
    }

    // blockquote
    if (trimmed.startsWith('> ')) {
      flushParagraph()
      flushList()
      flushTable()
      blockquoteLines.push(trimmed.slice(2))
      inBlockquote = true
      continue
    }
    if (inBlockquote && !trimmed.startsWith('> ')) {
      flushBlockquote()
    }

    // 無序列表 - x
    const ul = /^[-*]\s+(.+)$/.exec(trimmed)
    if (ul) {
      flushParagraph()
      flushTable()
      flushBlockquote()
      if (listType !== 'ul') {
        flushList()
        listType = 'ul'
      }
      listItems.push(inlineLine(ul[1]))
      continue
    }

    // 有序列表 1. x
    const ol = /^\d+\.\s+(.+)$/.exec(trimmed)
    if (ol) {
      flushParagraph()
      flushTable()
      flushBlockquote()
      if (listType !== 'ol') {
        flushList()
        listType = 'ol'
      }
      listItems.push(inlineLine(ol[1]))
      continue
    }

    // 段落（連續行）
    if (listType) flushList()
    if (tableHeaders) flushTable()
    paragraph.push(trimmed)
  }

  flushAll()
  return out.join('\n')
}
