#!/usr/bin/env node
/**
 * RobotsAsia.com product importer.
 *
 * Reads a batch JSON config (or a single --url) of {url, useCases} entries,
 * scrapes each product page with cheerio, downloads the main image(s) via
 * sharp (WebP, max 1200x1200), and emits:
 *
 *   public/assets/products/solutions/<useCase>/<slug>-<n>.webp   ← images
 *   src/data/robotsasia-products.generated.json                  ← raw scraped data
 *   src/data/robotsasia-products.generated.ts                    ← Robot[] TS snippet
 *   src/data/robotsasia-import-report.json                       ← per-URL status
 *
 * Each output product is marked draft (needsManualReview: true) and uses
 * EN strings for both fa and en fields — you translate manually before
 * pasting into `src/data/robots.ts`.
 *
 * Respects robots.txt (skips disallowed paths), throttles between requests,
 * retries transient errors, and dedupes by SKU + URL.
 *
 * Usage:
 *   node scripts/import-robotsasia.mjs --batch=scripts/robotsasia-import.json
 *   node scripts/import-robotsasia.mjs --url=https://www.robotsasia.com/<slug>.htm --useCases=education
 *   node scripts/import-robotsasia.mjs --batch=... --dry-run
 *   node scripts/import-robotsasia.mjs --batch=... --delay=2000 --max-images=3
 */

import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as sleep } from 'node:timers/promises'

import * as cheerio from 'cheerio'
import sharp from 'sharp'

// ===== Paths =====
const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')
const OUT_DIR = join(ROOT, 'src/data')
const ASSETS_ROOT_BASE = join(ROOT, 'public/assets/products')

// ===== CLI =====
const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const [k, ...rest] = a.replace(/^--/, '').split('=')
    return [k, rest.length ? rest.join('=') : 'true']
  }),
)
const BATCH = args.batch
const SINGLE_URL = args.url
const SINGLE_USE_CASES = (args.useCases || '').split(',').filter(Boolean)
const DRY_RUN = args['dry-run'] === 'true'
const DELAY_MS = Number(args.delay ?? 2000)
const MAX_IMAGES = Number(args['max-images'] ?? 1)
const OVERWRITE = args['overwrite-images'] === 'true'
const MAX_RETRIES = Number(args.retries ?? 3)
const UA = 'IranRobotImporter/1.0 (+contact your-email)'

// Output filename prefix. Defaults to the solutions-flavored name for backward compat.
const OUT_PREFIX = args.out ?? 'robotsasia-products'
const JSON_OUT = join(OUT_DIR, `${OUT_PREFIX}.generated.json`)
const TS_OUT = join(OUT_DIR, `${OUT_PREFIX}.generated.ts`)
const REPORT_OUT = join(
  OUT_DIR,
  OUT_PREFIX === 'robotsasia-products'
    ? 'robotsasia-import-report.json'
    : `${OUT_PREFIX}-import-report.json`,
)

const VALID_USE_CASES = new Set([
  'education',
  'warehouse',
  'inspection',
  'security',
  'healthcare',
  'custom',
])

const VALID_ACCESSORY_SUBS = new Set([
  'robot-arms',
  'robot-batteries',
  'robot-chargers',
  'robot-hands',
  'sensors',
])

const VALID_HUMANOID_SUBS = new Set([
  'bipedal-humanoids',
  'wheeled-humanoids',
  'upper-body-humanoids',
])

const VALID_QUADRUPED_SUBS = new Set([
  'standard-quadrupeds',
  'wheeled-quadrupeds',
])

/**
 * Given a batch item, return the relative folder name under public/assets/products/
 * for image storage. Returns { dir, rel } where rel is also the URL path stem.
 */
function resolveAssetFolder(item) {
  if (item.category === 'accessories') {
    if (!item.subcategory) throw new Error('accessory item missing subcategory')
    if (!VALID_ACCESSORY_SUBS.has(item.subcategory)) {
      throw new Error(`invalid accessory subcategory: ${item.subcategory}`)
    }
    return {
      dir: join(ASSETS_ROOT_BASE, 'accessories', item.subcategory),
      rel: `/assets/products/accessories/${item.subcategory}`,
    }
  }
  if (item.category === 'humanoid') {
    if (!item.subcategory) throw new Error('humanoid item missing subcategory')
    if (!VALID_HUMANOID_SUBS.has(item.subcategory)) {
      throw new Error(`invalid humanoid subcategory: ${item.subcategory}`)
    }
    return {
      dir: join(ASSETS_ROOT_BASE, 'humanoids', item.subcategory),
      rel: `/assets/products/humanoids/${item.subcategory}`,
    }
  }
  if (item.category === 'quadruped') {
    if (!item.subcategory) throw new Error('quadruped item missing subcategory')
    if (!VALID_QUADRUPED_SUBS.has(item.subcategory)) {
      throw new Error(`invalid quadruped subcategory: ${item.subcategory}`)
    }
    return {
      dir: join(ASSETS_ROOT_BASE, 'quadrupeds', item.subcategory),
      rel: `/assets/products/quadrupeds/${item.subcategory}`,
    }
  }
  // Default: solutions mode keyed off first useCase
  const uc = item.useCases?.[0]
  if (!uc) throw new Error('item missing useCases (solutions mode)')
  return {
    dir: join(ASSETS_ROOT_BASE, 'solutions', uc),
    rel: `/assets/products/solutions/${uc}`,
  }
}

// ===== robots.txt cache =====
let robotsTxt = null
async function loadRobotsTxt() {
  if (robotsTxt !== null) return robotsTxt
  const res = await fetch('https://www.robotsasia.com/robots.txt', {
    headers: { 'User-Agent': UA },
  })
  robotsTxt = res.ok ? await res.text() : ''
  return robotsTxt
}
async function isAllowedByRobots(pathname) {
  const txt = await loadRobotsTxt()
  if (!txt) return true
  // simplistic parser: collect Disallow lines under "User-agent: *"
  const lines = txt.split('\n').map((l) => l.trim())
  let inStar = false
  const disallow = []
  for (const line of lines) {
    if (!line || line.startsWith('#')) continue
    const [k, v] = line.split(':').map((x) => (x ?? '').trim())
    if (k.toLowerCase() === 'user-agent') inStar = v === '*'
    if (inStar && k.toLowerCase() === 'disallow' && v) disallow.push(v)
  }
  return !disallow.some((p) => pathname.startsWith(p))
}

// ===== Fetch with retry =====
async function fetchWithRetry(url, init = {}) {
  let lastErr
  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const res = await fetch(url, {
        ...init,
        headers: { 'User-Agent': UA, ...(init.headers ?? {}) },
      })
      if (res.status === 429 || res.status >= 500) {
        throw new Error(`HTTP ${res.status}`)
      }
      return res
    } catch (err) {
      lastErr = err
      const backoff = DELAY_MS * attempt
      console.warn(`  retry ${attempt}/${MAX_RETRIES} after ${backoff}ms: ${err.message}`)
      await sleep(backoff)
    }
  }
  throw lastErr
}

// ===== Slug helpers =====
function slugFromUrl(url) {
  const u = new URL(url)
  const base = u.pathname.split('/').pop() ?? ''
  return base
    .replace(/\.htm$/i, '')
    .replace(/^\/+|\/+$/g, '')
    .replace(/[^a-zA-Z0-9-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
    .toLowerCase()
}

function slugify(str) {
  return str
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

// ===== Price parser =====
// "CN¥111,509.41 (As low as CN¥83,632.06)" → { amount: 111509.41, currency: 'CNY', raw: 'CN¥111,509.41' }
function parsePrice(raw) {
  if (!raw) return null
  const text = raw.replace(/\s+/g, ' ').trim()
  const m = text.match(/(CN¥|¥|USD|US\$|\$|€|£|HK\$)\s*([\d,]+(?:\.\d+)?)/i)
  if (!m) return null
  const symbol = m[1]
  const amount = Number(m[2].replace(/,/g, ''))
  const currency =
    /CN¥|¥/i.test(symbol) ? 'CNY' :
    /USD|US\$|\$/i.test(symbol) ? 'USD' :
    /€/.test(symbol) ? 'EUR' :
    /£/.test(symbol) ? 'GBP' :
    /HK\$/i.test(symbol) ? 'HKD' : 'CNY'
  return { amount, currency, raw: text }
}

// ===== HTML extraction =====
function extractProduct($, url) {
  const pickFirst = (sels, fn = (el) => $(el).text().trim()) => {
    for (const sel of sels) {
      const el = $(sel).first()
      if (el.length) {
        const v = fn(el)
        if (v) return v
      }
    }
    return null
  }

  const name =
    pickFirst(['h1.page-title', 'h1[itemprop="name"]', 'h1.product-name', 'h1']) || null
  const sku =
    pickFirst([
      '[itemprop="sku"]',
      '.product.attribute.sku .value',
      '.sku .value',
    ]) || null
  const priceRaw =
    pickFirst([
      '[data-price-type="finalPrice"]',
      '.price-final_price .price',
      '.product-info-price .price',
      '.price',
    ]) || null
  const description =
    pickFirst([
      '#description',
      '[itemprop="description"]',
      '.product.attribute.description .value',
      '.description',
    ], (el) => $(el).text().trim().replace(/\s+/g, ' ')) || null

  // Specs table: tbody tr th/td
  const specs = []
  $('#product-attribute-specs-table tbody tr, .additional-attributes tbody tr, table.data-table tbody tr').each(
    (_, tr) => {
      const label = $(tr).find('th, td').first().text().trim()
      const value = $(tr).find('td').last().text().trim()
      if (label && value && label !== value) {
        specs.push({ label, value })
      }
    },
  )

  // Brand inference: from name (first token) or from breadcrumb manufacturer
  let brand =
    pickFirst([
      '[itemprop="brand"]',
      '.product-info-brand',
    ]) ||
    (name ? name.split(/\s+/)[0] : null)

  // Hero image: prefer Magento's standard signals, fallback to first /media/catalog/product/.
  // Dedupe by filename basename so cache variants (image_300.jpg vs image_1024.jpg) collapse.
  const heroCandidates = []
  const push = (v) => {
    if (!v) return
    const full = v.startsWith('//') ? `https:${v}` : v
    if (!/\/media\/catalog\/product\//.test(full)) return
    if (/placeholder|swatch|small_image|thumbnail/i.test(full)) return
    heroCandidates.push(full)
  }
  // Highest-resolution hero first; smaller social-card og:image last.
  push($('[data-zoom-image]').first().attr('data-zoom-image'))
  push($('.gallery-placeholder img').first().attr('src'))
  push($('.fotorama__img').first().attr('src'))
  push($('[itemprop="image"]').attr('content') || $('[itemprop="image"]').attr('src'))
  push($('meta[property="og:image"]').attr('content'))
  // Catch-all: every img on the page in DOM order
  $('img').each((_, el) => {
    push($(el).attr('data-zoom-image') || $(el).attr('src') || '')
  })

  // Dedupe by filename basename (strips Magento cache hash directories)
  const seenBase = new Set()
  const imageUrls = []
  for (const u of heroCandidates) {
    const base = u.split('/').pop()?.toLowerCase() ?? ''
    if (!base || seenBase.has(base)) continue
    seenBase.add(base)
    imageUrls.push(u)
    if (imageUrls.length >= MAX_IMAGES) break
  }

  return {
    sourceUrl: url,
    name,
    brand,
    sku,
    price: parsePrice(priceRaw),
    description,
    specs,
    imageUrls,
  }
}

// ===== Image download =====
async function downloadAndConvertImage(imageUrl, destPath) {
  if (!OVERWRITE) {
    try {
      await stat(destPath)
      return { skipped: true, destPath }
    } catch {
      // not present, continue
    }
  }
  const res = await fetchWithRetry(imageUrl)
  if (!res.ok) throw new Error(`image fetch ${res.status}`)
  const buf = Buffer.from(await res.arrayBuffer())
  await mkdir(dirname(destPath), { recursive: true })
  await sharp(buf)
    .resize({
      width: 1200,
      height: 1200,
      fit: 'inside',
      withoutEnlargement: true,
    })
    .webp({ quality: 86 })
    .toFile(destPath)
  return { skipped: false, destPath }
}

// ===== Build Robot object (TS-friendly draft) =====
function buildRobotDraft(extracted, useCases, category, subcategory) {
  const idSlug = slugify(extracted.name || slugFromUrl(extracted.sourceUrl))
  const priceLabelEn = extracted.price
    ? `${extracted.price.raw} (${extracted.price.currency})`
    : 'Request quote'

  return {
    needsManualReview: true,
    sourceUrl: extracted.sourceUrl,
    id: idSlug,
    slug: idSlug,
    name: extracted.name, // TODO: translate to fa
    nameEn: extracted.name,
    brand: extracted.brand ?? '—',
    model: extracted.sku ?? extracted.name,
    origin: '—', // TODO: fill manually
    originEn: '—',
    // Category MUST be a real form-factor value (humanoid/quadruped/amr/ugv/drone/cobots/accessories/etc).
    // Solutions is NOT a form-factor — it's a useCase. Never set category to 'solutions'.
    category: category ?? 'TODO',
    subcategory: subcategory ?? undefined,
    isNewArrival: true,
    useCases: category === 'accessories' ? [] : useCases,
    tags: [],
    tagline: extracted.description?.slice(0, 200) ?? '',
    taglineEn: extracted.description?.slice(0, 200) ?? '',
    description: extracted.description ?? '',
    descriptionEn: extracted.description ?? '',
    priceLabel: priceLabelEn, // TODO: translate to fa
    priceLabelEn,
    priceSource: extracted.price ?? null,
    leadTimeDays: 30,
    inStock: true,
    modes: ['procure'],
    specs: extracted.specs.map((s) => ({ label: s.label, value: s.value })),
    specsEn: extracted.specs.map((s) => ({ label: s.label, value: s.value })),
    highlights: [],
    highlightsEn: [],
    sourceImageUrls: extracted.imageUrls,
    image: null, // filled after images are written
    gallery: [], // filled after images are written
  }
}

// ===== Main =====
async function main() {
  // Load batch
  let items = []
  if (BATCH) {
    const txt = await readFile(BATCH, 'utf8')
    items = JSON.parse(txt)
  } else if (SINGLE_URL) {
    items = [{ url: SINGLE_URL, useCases: SINGLE_USE_CASES }]
  } else {
    console.error('Usage: --batch=<path.json> OR --url=<url> --useCases=education[,...]')
    process.exit(1)
  }

  // Validate
  items = items.filter((item) => {
    if (!item?.url) {
      console.warn('skip: missing url', item)
      return false
    }
    if (item.category === 'accessories') {
      if (!item.subcategory) {
        console.warn(`skip ${item.url}: accessory missing subcategory`)
        return false
      }
      if (!VALID_ACCESSORY_SUBS.has(item.subcategory)) {
        console.warn(`skip ${item.url}: invalid accessory subcategory ${item.subcategory}`)
        return false
      }
      return true
    }
    if (item.category === 'humanoid' || item.category === 'quadruped') {
      const validSet = item.category === 'humanoid' ? VALID_HUMANOID_SUBS : VALID_QUADRUPED_SUBS
      if (!item.subcategory) {
        console.warn(`skip ${item.url}: ${item.category} missing subcategory`)
        return false
      }
      if (!validSet.has(item.subcategory)) {
        console.warn(`skip ${item.url}: invalid ${item.category} subcategory ${item.subcategory}`)
        return false
      }
      return true
    }
    // Default solutions mode: must have at least one valid useCase.
    const uc = item.useCases ?? []
    if (uc.length === 0) {
      console.warn(`skip ${item.url}: no useCases`)
      return false
    }
    const bad = uc.filter((u) => !VALID_USE_CASES.has(u))
    if (bad.length) {
      console.warn(`skip ${item.url}: invalid useCases ${bad.join(', ')}`)
      return false
    }
    return true
  })

  console.log(`Importing ${items.length} item(s). DRY_RUN=${DRY_RUN}`)

  // Existing generated data (for dedup across runs)
  let existing = []
  try {
    existing = JSON.parse(await readFile(JSON_OUT, 'utf8'))
  } catch {
    existing = []
  }
  const seen = new Set(existing.map((r) => r.sourceUrl))
  const skuSeen = new Set(existing.map((r) => r.model).filter(Boolean))

  const report = { startedAt: new Date().toISOString(), results: [] }
  const out = [...existing]

  for (const [i, item] of items.entries()) {
    const { url, useCases } = item
    console.log(`\n[${i + 1}/${items.length}] ${url}`)

    if (seen.has(url)) {
      console.log('  skip: already imported (sourceUrl dedup)')
      report.results.push({ url, status: 'skipped', reason: 'duplicate url' })
      continue
    }

    const u = new URL(url)
    if (!(await isAllowedByRobots(u.pathname))) {
      console.log(`  skip: disallowed by robots.txt (${u.pathname})`)
      report.results.push({ url, status: 'skipped', reason: 'robots.txt' })
      continue
    }

    try {
      const res = await fetchWithRetry(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const html = await res.text()
      const $ = cheerio.load(html)
      const extracted = extractProduct($, url)

      if (!extracted.name) {
        report.results.push({ url, status: 'failed', reason: 'no name extracted' })
        console.log('  fail: could not extract product name')
        await sleep(DELAY_MS)
        continue
      }

      if (extracted.sku && skuSeen.has(extracted.sku)) {
        console.log(`  skip: duplicate SKU ${extracted.sku}`)
        report.results.push({ url, status: 'skipped', reason: 'duplicate sku' })
        await sleep(DELAY_MS)
        continue
      }

      const draft = buildRobotDraft(extracted, useCases, item.category, item.subcategory)

      // Compute image destination based on whether this is an accessory or a solutions item.
      const { dir: imgDir, rel: imgRelDir } = resolveAssetFolder(item)
      const primaryBucket =
        item.category === 'accessories' ||
        item.category === 'humanoid' ||
        item.category === 'quadruped'
          ? item.subcategory
          : useCases?.[0]
      const writtenImages = []
      if (!DRY_RUN) {
        for (let n = 0; n < extracted.imageUrls.length; n++) {
          const src = extracted.imageUrls[n]
          const filename = `${draft.slug}${n === 0 ? '' : `-${n + 1}`}.webp`
          const destPath = join(imgDir, filename)
          try {
            await downloadAndConvertImage(src, destPath)
            writtenImages.push(`${imgRelDir}/${filename}`)
            console.log(`  ✓ image ${n + 1}/${extracted.imageUrls.length}`)
          } catch (err) {
            console.warn(`  ! image ${n + 1} failed: ${err.message}`)
          }
        }
      } else {
        for (let n = 0; n < extracted.imageUrls.length; n++) {
          const filename = `${draft.slug}${n === 0 ? '' : `-${n + 1}`}.webp`
          writtenImages.push(`${imgRelDir}/${filename}`)
        }
      }

      draft.image = writtenImages[0] ?? null
      draft.gallery = writtenImages

      out.push(draft)
      seen.add(url)
      if (extracted.sku) skuSeen.add(extracted.sku)
      report.results.push({
        url,
        status: 'imported',
        sku: extracted.sku,
        images: writtenImages.length,
        bucket: primaryBucket,
        category: item.category ?? null,
        subcategory: item.subcategory ?? null,
      })
      console.log(`  ✓ imported "${extracted.name}"`)
    } catch (err) {
      console.error(`  FAIL: ${err.message}`)
      report.results.push({ url, status: 'failed', reason: err.message })
    }

    await sleep(DELAY_MS)
  }

  if (DRY_RUN) {
    console.log('\nDRY_RUN: not writing output files. Would have written:')
    console.log(`  ${JSON_OUT}  (${out.length} total)`)
    console.log(`  ${TS_OUT}`)
    console.log(`  ${REPORT_OUT}`)
    return
  }

  await mkdir(OUT_DIR, { recursive: true })
  await writeFile(JSON_OUT, JSON.stringify(out, null, 2))
  await writeFile(REPORT_OUT, JSON.stringify(report, null, 2))
  await writeFile(TS_OUT, renderTs(out))

  console.log(`\nWrote ${out.length} draft product(s).`)
  console.log(`  ${JSON_OUT}`)
  console.log(`  ${TS_OUT}`)
  console.log(`  ${REPORT_OUT}`)
  console.log('\nNext steps:')
  console.log('  1. Review src/data/robotsasia-products.generated.ts.')
  console.log('  2. Translate name/tagline/description/specs labels to Persian.')
  console.log('  3. Set correct category (humanoid/quadruped/amr/ugv/drone/solutions/cobots).')
  console.log('  4. Set correct origin (country).')
  console.log('  5. Paste cleaned entries into src/data/robots.ts.')
}

function renderTs(products) {
  const header = [
    '/**',
    ' * AUTOGENERATED by scripts/import-robotsasia.mjs.',
    ' * Do NOT edit — re-run the importer to regenerate.',
    ' * Review each entry before pasting into src/data/robots.ts.',
    ' */',
    "import type { Robot } from '../types'",
    '',
    'export const ROBOTSASIA_DRAFTS: (Robot & { needsManualReview?: boolean; sourceUrl?: string })[] = [',
  ].join('\n')
  const body = products
    .map((p) => `  ${JSON.stringify(p, null, 2).replace(/\n/g, '\n  ')},`)
    .join('\n')
  return `${header}\n${body}\n]\n`
}

main().catch((err) => {
  console.error('Fatal:', err)
  process.exit(1)
})
