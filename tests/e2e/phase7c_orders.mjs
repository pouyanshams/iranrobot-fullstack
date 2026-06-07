/**
 * Phase 7C E2E -- customer sees their Sales Order in #/account/orders.
 *
 * 1) Login as customer1 (who has SAL-ORD-2026-00001 from the backend smoke)
 * 2) Confirm Orders sidebar entry exists
 * 3) Open #/account/orders -> list shows the SO with status / total
 * 4) Click row -> drawer opens with items + linked records
 * 5) Open #/account (Overview) -> Orders count card present
 * 6) Drawer overflow + page sanity at 1440 + 390
 * 7) Phase 7A.1, 7B, 6 surfaces still reachable (sidebar links present)
 */

import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase7c-orders'
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

console.log('=== Phase 7C E2E ===\n')

// 1) Login
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

// 2) Overview shows Orders count card
console.log('\n[2] Overview Orders count card')
await page.goto('http://localhost:5173/#/account', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1500))
await snap('overview', 1)
const overviewText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Overview shows Orders count card', /(سفارش‌ها|Orders)/.test(overviewText))

// Probe via API to know how many orders to expect
const apiOrders = await page.evaluate(async () => {
  const r = await fetch('/api/method/iranrobot_backend.api.orders.get_my_orders?limit=50', { credentials: 'include' })
  return (await r.json()).message
})
const ordersFromApi = (apiOrders.data && apiOrders.data.orders) || []
console.log(`    API orders: ${ordersFromApi.length}`)
check('API returns at least 1 order for customer1', ordersFromApi.length >= 1)

// 3) Sidebar has Orders link
console.log('\n[3] Sidebar has Orders entry')
const sidebarText = await page.evaluate(() => document.querySelector('aside')?.innerText || '')
check('Sidebar lists Orders entry', /(سفارش‌ها|Orders)/.test(sidebarText))

// 4) Open #/account/orders
console.log('\n[4] Open #/account/orders')
await page.goto('http://localhost:5173/#/account/orders', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1800))
await snap('orders_list', 2)
const ordersText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Orders page renders header', /(سفارش‌ها|Orders)/.test(ordersText))

if (ordersFromApi.length > 0) {
  const soName = ordersFromApi[0].name
  check('SO id (SAL-ORD-...) visible in list', ordersText.includes(soName), `expected=${soName}`)

  // 5) Open detail drawer
  console.log('\n[5] Open order detail drawer')
  await page.evaluate((name) => {
    const rows = document.querySelectorAll('main ul li button')
    for (const r of rows) {
      const monos = r.querySelectorAll('.font-mono, [class*="font-mono"]')
      for (const m of monos) {
        if ((m.textContent || '').trim() === name) { r.click(); return }
      }
    }
  }, soName)
  await new Promise(r => setTimeout(r, 1500))
  await snap('order_detail', 3)
  const drawerText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Detail drawer opens', drawerText.length > 0)
  check('Drawer shows SO id', drawerText.includes(soName))
  check('Drawer shows Items section', /(اقلام سفارش|Items)/.test(drawerText))
  check('Drawer shows linked Quotation', /(پیوندها|Linked records)/.test(drawerText))
  // Inspect actual <button> elements (ignore the footnote that mentions
  // "invoicing" / "payment" in a "we don't do that here" sentence).
  const drawerButtonLabels = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"][aria-modal="true"]')
    return Array.from(d?.querySelectorAll('button') || []).map(b => (b.textContent || '').trim())
  })
  const hasAnyForbiddenAction = drawerButtonLabels.some(label =>
    /(Pay Now|Pay\b|پرداخت|Invoice\b|صدور صورتحساب|Cancel order|لغو سفارش|Reorder|سفارش مجدد)/.test(label)
  )
  check('Drawer is read-only -- no Pay / Invoice / Cancel / Reorder buttons', !hasAnyForbiddenAction, `buttons=${JSON.stringify(drawerButtonLabels)}`)

  // 6) Overflow checks
  console.log('\n[6] Drawer overflow sanity')
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
  await snap('order_detail_mobile', 4)
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

// 7) Phase 7A.1 / 7B / Phase 6 surfaces still reachable
console.log('\n[7] Other dashboard pages still load')
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
