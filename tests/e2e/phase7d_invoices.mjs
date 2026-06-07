/**
 * Phase 7D E2E -- customer sees their Sales Invoice + payments in
 * #/account/invoices.
 *
 * Pre-seeded by the Phase 7D backend smoke:
 *   QR-2026-00094 / 00096 → ACC-SINV-... → ACC-PAY-... (partly paid)
 */

import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase7d-invoices'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const browser = await puppeteer.launch({
  executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: 'new',
  args: ['--no-sandbox'],
})
const page = await browser.newPage()
await page.setViewport({ width: 1440, height: 900 })

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

console.log('=== Phase 7D E2E ===\n')

// Login
console.log('[1] Login as customer1')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 700))
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 800))
await page.waitForSelector('[aria-labelledby="login-title"] input[type="email"]', { timeout: 5000 })
await reactSet('[aria-labelledby="login-title"] input[type="email"]', 'customer1@example.com')
await reactSet('[aria-labelledby="login-title"] input[type="password"]', 'ChangeMe-123')
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2500))

// 2) Overview shows Invoices count card
console.log('\n[2] Overview Invoices count card')
await page.goto('http://localhost:5173/#/account', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1800))
await snap('overview', 1)
const overviewText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Overview shows Invoices count card', /(صورتحساب‌ها|Invoices)/.test(overviewText))

const apiInvoices = await page.evaluate(async () => {
  const r = await fetch('/api/method/iranrobot_backend.api.invoices.get_my_invoices?limit=50', { credentials: 'include' })
  return (await r.json()).message
})
const invoicesFromApi = (apiInvoices.data && apiInvoices.data.invoices) || []
console.log(`    API invoices: ${invoicesFromApi.length}`)
check('API returns at least 1 invoice for customer1', invoicesFromApi.length >= 1)

// 3) Sidebar has Invoices link
console.log('\n[3] Sidebar has Invoices entry')
const sidebarText = await page.evaluate(() => document.querySelector('aside')?.innerText || '')
check('Sidebar lists Invoices entry', /(صورتحساب‌ها|Invoices)/.test(sidebarText))

// 4) Open #/account/invoices
console.log('\n[4] Open #/account/invoices')
await page.goto('http://localhost:5173/#/account/invoices', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1800))
await snap('invoices_list', 2)
const invoicesText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Invoices page renders header', /(صورتحساب‌ها|Invoices)/.test(invoicesText))

if (invoicesFromApi.length > 0) {
  const siName = invoicesFromApi[0].name
  check('SI id (ACC-SINV-...) visible in list', invoicesText.includes(siName), `expected=${siName}`)
  check('Outstanding total or Outstanding line visible', /(باقی‌مانده|Outstanding)/.test(invoicesText))

  // 5) Open detail drawer
  console.log('\n[5] Open invoice detail drawer')
  await page.evaluate((name) => {
    const rows = document.querySelectorAll('main ul li button')
    for (const r of rows) {
      const monos = r.querySelectorAll('.font-mono, [class*="font-mono"]')
      for (const m of monos) {
        if ((m.textContent || '').trim() === name) { r.click(); return }
      }
    }
  }, siName)
  await new Promise(r => setTimeout(r, 1500))
  await snap('invoice_detail', 3)
  const drawerText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Detail drawer opens', drawerText.length > 0)
  check('Drawer shows SI id', drawerText.includes(siName))
  check('Drawer shows Items section', /(اقلام صورتحساب|Items)/.test(drawerText))
  check('Drawer shows Financial summary', /(مالی|Financial summary)/.test(drawerText))
  check('Drawer shows Outstanding line', /(باقی‌مانده|Outstanding)/.test(drawerText))

  // Payment summary should appear because the smoke seeded a PE
  check('Drawer shows Recorded payments section', /(پرداخت‌های ثبت‌شده|Recorded payments)/.test(drawerText))

  // Read-only -- no Pay Now / Download / Refund buttons
  const drawerButtonLabels = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"][aria-modal="true"]')
    return Array.from(d?.querySelectorAll('button') || []).map(b => (b.textContent || '').trim())
  })
  const hasForbidden = drawerButtonLabels.some(l =>
    /(Pay Now|Pay\b|پرداخت کنید|Download|دانلود|Refund|بازپرداخت|Cancel invoice|لغو صورتحساب)/.test(l)
  )
  check('Drawer is read-only -- no Pay / Download / Refund / Cancel buttons', !hasForbidden, `buttons=${JSON.stringify(drawerButtonLabels)}`)

  // Overflow checks
  const at1440 = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"][aria-modal="true"]')
    const sa = d?.querySelector('.overflow-y-auto')
    return {
      sw: sa?.scrollWidth, cw: sa?.clientWidth,
      bw: document.body.clientWidth, bsw: document.body.scrollWidth,
    }
  })
  check('Drawer no horizontal overflow at 1440', (at1440.sw||0) <= (at1440.cw||0)+1)
  check('Page no horizontal overflow at 1440', at1440.bsw <= at1440.bw+1)

  await page.setViewport({ width: 390, height: 844 })
  await new Promise(r => setTimeout(r, 600))
  await snap('invoice_detail_mobile', 4)
  const at390 = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"][aria-modal="true"]')
    const sa = d?.querySelector('.overflow-y-auto')
    return {
      drawerW: d?.clientWidth, viewportW: window.innerWidth,
      sw: sa?.scrollWidth, cw: sa?.clientWidth,
      bw: document.body.clientWidth, bsw: document.body.scrollWidth,
    }
  })
  check('Mobile drawer fits viewport', at390.drawerW <= at390.viewportW)
  check('Mobile drawer no horizontal overflow', (at390.sw||0) <= (at390.cw||0)+1)
  check('Mobile page no horizontal overflow', at390.bsw <= at390.bw+1)
  await page.setViewport({ width: 1440, height: 900 })
}

// 6) Other dashboard pages still load
console.log('\n[6] Other dashboard pages still load')
await page.goto('http://localhost:5173/#/account/orders', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1500))
const ordersText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Orders (Phase 7C) still loads', /(سفارش‌ها|Orders)/.test(ordersText))

await page.goto('http://localhost:5173/#/account/profile', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1500))
const profileText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Profile + Addresses (7A.1) still loads', /(آدرس‌ها|Addresses)/.test(profileText))

await page.goto('http://localhost:5173/#/account/quotes', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1500))
const quotesText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Quotes (Phase 7B accept/reject) still loads', /(استعلام‌ها|Quote requests)/.test(quotesText))

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
