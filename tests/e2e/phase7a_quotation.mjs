import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase7a-quotation'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1400, height: 900 })

const pageErrors = []
const consoleErr = []
page.on('pageerror', e => pageErrors.push({ message: e.message }))
page.on('console', m => { if (m.type() === 'error') consoleErr.push({ text: m.text() }) })

async function dismissOnboarding() {
  await page.evaluate(() => {
    for (const d of document.querySelectorAll('[role="dialog"]')) {
      if (d.querySelector('[aria-labelledby="login-title"]')) continue
      for (const b of d.querySelectorAll('button')) {
        if (/(رد شدن|Skip|بستن|Close)/.test(b.textContent || '')) { b.click(); return }
      }
    }
  })
  await new Promise(r => setTimeout(r, 400))
}

async function reactSet(selector, value) {
  await page.evaluate((sel, val) => {
    const el = document.querySelector(sel)
    if (!el) return
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value)
}

async function snap(name, n) {
  await new Promise(r => setTimeout(r, 600))
  await page.screenshot({ path: `${SHOTS}/${String(n).padStart(2,'0')}_${name}.png` })
}

const PASS = []
const FAIL = []
function check(label, ok, extra='') {
  if (ok) { PASS.push(label); console.log(`  ✅ ${label}`) }
  else { FAIL.push(label); console.log(`  ❌ ${label} ${extra}`) }
}

console.log('=== Phase 7A E2E ===\n')

// 1. Log in as customer1 + go to quotes list
console.log('[1] Login + navigate to /#/account/quotes')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 700))
// Open login modal
const opened = await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return true }
  }
  return false
})
console.log(`    login button click: ${opened}`)
await new Promise(r => setTimeout(r, 800))
await page.waitForSelector('[aria-labelledby="login-title"] input[type="email"]', { timeout: 5000 })
await reactSet('[aria-labelledby="login-title"] input[type="email"]', 'customer1@example.com')
await reactSet('[aria-labelledby="login-title"] input[type="password"]', 'ChangeMe-123')
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2500))
await page.goto('http://localhost:5173/#/account/quotes', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1200))
await snap('quotes_list', 1)
const listText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Quote list shows real QR ids', /QR-\d+-\d+/.test(listText))

// 2. Open the QR seeded by the Phase 7A E2E fixture. Reading from a known
//    fixture (instead of walking the customer's quote list) keeps this
//    assertion deterministic when Phase 7B/7C/7D smokes mutate other QRs
//    in the same customer1 namespace.
console.log('\n[2] Read fixture + open the seeded quote from the list')
const FIXTURE_PATH = 'tests/artifacts/phase7a_e2e_fixture.json'
let convertedName = null
let fixtureQuotationId = null
let fixtureStatus = null
if (!fs.existsSync(FIXTURE_PATH)) {
  console.log(`    ❌ MISSING FIXTURE -- run:`)
  console.log(`        bench --site iranrobot.localhost execute iranrobot_backend.commands._phase7_e2e_fixtures.seed_phase7a_e2e_fixture`)
  FAIL.push('Phase 7A fixture present')
} else {
  try {
    const raw = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf-8'))
    convertedName = raw.qr_name || null
    fixtureQuotationId = raw.quotation_id || null
    fixtureStatus = raw.quotation_status || null
  } catch (e) {
    console.log(`    ❌ fixture JSON parse error: ${e.message}`)
  }
}
console.log(`    fixture qr=${convertedName} qid=${fixtureQuotationId} status=${fixtureStatus}`)
check('Phase 7A fixture provides a seeded QR', !!convertedName)

if (convertedName) {
  // Click the matching row in the list
  await page.evaluate((name) => {
    const rows = document.querySelectorAll('main ul li button')
    for (const r of rows) {
      const monos = r.querySelectorAll('.font-mono, [class*="font-mono"]')
      for (const m of monos) {
        if ((m.textContent || '').trim() === name) { r.click(); return }
      }
    }
  }, convertedName)
  await new Promise(r => setTimeout(r, 1200))
  await snap('quote_detail_with_quotation', 2)

  const drawerText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Detail drawer opens', drawerText.length > 0)
  check('Drawer shows Quotation panel header', /(پیشنهاد قیمت|Quotation)/.test(drawerText))
  check('Drawer shows Quotation id (SAL-QTN-)', /SAL-QTN-\d+-\d+/.test(drawerText), drawerText.slice(0, 220))
  check('Drawer shows status badge (Draft/Sent)', /(پیش‌نویس|Draft|ارسال شد|Sent)/.test(drawerText))
  check('Drawer shows Quoted total label', /(مجموع پیشنهاد|Quoted total)/.test(drawerText))
  check('No accept/reject buttons exist in 7A', !/(پذیرفتن|Accept this|Reject this)/.test(drawerText))

  // Close drawer
  await page.evaluate(() => {
    const btn = document.querySelector('[role="dialog"] button[aria-label]')
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 400))
}

// 3. Open a quote that has NO linked Quotation -> drawer should look like before
console.log('\n[3] Open an unconverted quote -> no Quotation panel')
const unconvertedName = await page.evaluate(async () => {
  const r = await fetch('/api/method/iranrobot_backend.api.requests.get_my_requests?limit=50', {
    credentials: 'include',
    headers: { 'Accept': 'application/json' },
  })
  const env = (await r.json()).message
  const quotes = (env.data && env.data.quote_requests) || []
  for (const q of quotes) {
    const dr = await fetch(`/api/method/iranrobot_backend.api.requests.get_my_request_detail?kind=quote&name=${encodeURIComponent(q.name)}`, {
      credentials: 'include',
      headers: { 'Accept': 'application/json' },
    })
    const denv = (await dr.json()).message
    const rec = (denv.data && denv.data.record) || {}
    if (!rec.erpnext_quotation) return q.name
  }
  return null
})
console.log(`    unconverted quote: ${unconvertedName}`)
if (unconvertedName) {
  await page.evaluate((name) => {
    const rows = document.querySelectorAll('main ul li button')
    for (const r of rows) {
      const monos = r.querySelectorAll('.font-mono, [class*="font-mono"]')
      for (const m of monos) {
        if ((m.textContent || '').trim() === name) { r.click(); return }
      }
    }
  }, unconvertedName)
  await new Promise(r => setTimeout(r, 1200))
  await snap('quote_detail_without_quotation', 3)
  const drawerText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Unconverted quote drawer has NO Quotation header', !/SAL-QTN-/.test(drawerText), drawerText.slice(0,200))
}

// 4. Catalog still works
console.log('\n[4] Catalog still works')
await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 1500))
const catalogH1 = await page.evaluate(() => document.querySelector('main h1')?.textContent || '')
check('Catalog still renders', catalogH1.length > 0)

console.log('')
console.log(`  page errors:    ${pageErrors.length}`)
console.log(`  console errors: ${consoleErr.length}`)
pageErrors.forEach(e => console.log(`    ❌ ${e.message}`))
consoleErr.slice(0,4).forEach(m => console.log(`    [err] ${m.text.slice(0,300)}`))

console.log('')
console.log(`${PASS.length}/${PASS.length + FAIL.length} PASSED`)

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
process.exit(FAIL.length === 0 ? 0 : 1)
