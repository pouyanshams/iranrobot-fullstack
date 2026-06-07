/**
 * Phase 7B E2E: customer accept / reject quotation through the React drawer.
 *
 * Pre-flight: we need at least two Robot Quote Requests for customer1 whose
 * linked Quotation is in "Sent" state and customer_response is empty. We
 * provision them on the fly via bench-execute pre-step (file-based marker on
 * the iranrobot_backend.commands._phase7b_smoke module already does this).
 *
 * The puppeteer flow:
 *   1) Login as customer1
 *   2) #/account/quotes
 *   3) Find a Sent quote via API probe; open detail drawer
 *   4) Click Accept -> Confirm -> verify banner appears + buttons disappear
 *   5) Open another Sent quote; click Reject -> add note -> Confirm
 *   6) Verify rejection banner with the note
 *   7) Verify a Draft quote shows no accept/reject and shows the
 *      "not finalized" hint
 *   8) Drawer overflow + page overflow checks at 1440 and 390
 */

import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase7b-respond'
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
    const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value)
}

async function clickByText(needles, scopeSel = 'body') {
  return page.evaluate((arr, scope) => {
    const root = document.querySelector(scope) || document.body
    for (const b of root.querySelectorAll('button')) {
      const t = (b.textContent || '').trim()
      for (const n of arr) if (t.includes(n)) { b.click(); return t }
    }
    return null
  }, needles, scopeSel)
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

console.log('=== Phase 7B E2E ===\n')

// ---- 1. Login as customer1 ----
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

async function pickByState(predicate) {
  return page.evaluate(async (predFn) => {
    const fn = new Function('rec', 'return (' + predFn + ')(rec)')
    const r = await fetch('/api/method/iranrobot_backend.api.requests.get_my_requests?limit=80', { credentials: 'include' })
    const env = (await r.json()).message
    const list = (env.data && env.data.quote_requests) || []
    for (const q of list) {
      const dr = await fetch(`/api/method/iranrobot_backend.api.requests.get_my_request_detail?kind=quote&name=${encodeURIComponent(q.name)}`, { credentials: 'include' })
      const denv = (await dr.json()).message
      const rec = (denv.data && denv.data.record) || {}
      if (fn(rec)) return rec.name
    }
    return null
  }, predicate.toString())
}

async function openDrawer(name) {
  await page.evaluate((n) => {
    const rows = document.querySelectorAll('main ul li button')
    for (const r of rows) {
      const monos = r.querySelectorAll('.font-mono, [class*="font-mono"]')
      for (const m of monos) {
        if ((m.textContent || '').trim() === n) { r.click(); return }
      }
    }
  }, name)
  await new Promise(r => setTimeout(r, 1200))
}

await page.goto('http://localhost:5173/#/account/quotes', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1800))

// ---- 2. Accept flow ----
console.log('\n[2] Accept flow')
const acceptName = await pickByState((rec) => rec.can_respond === true)
console.log(`    candidate Sent quote: ${acceptName}`)
check('found a Sent quote to accept', !!acceptName)
if (acceptName) {
  await openDrawer(acceptName)
  await snap('accept_drawer_initial', 1)
  const initialText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Accept/Reject buttons present', /(پذیرش پیشنهاد|Accept quotation)/.test(initialText) && /(رد پیشنهاد|Reject quotation)/.test(initialText))

  // Click Accept -> Confirm panel appears
  await clickByText(['پذیرش پیشنهاد', 'Accept quotation'], '[role="dialog"]')
  await new Promise(r => setTimeout(r, 600))
  const confirmText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Accept confirm panel appears', /(تأیید پذیرش|Confirm acceptance)/.test(confirmText))

  // Click "Yes, accept"
  await clickByText(['بله، می‌پذیرم', 'Yes, accept'], '[role="dialog"]')
  await new Promise(r => setTimeout(r, 2500))
  await snap('accept_after_submit', 2)

  const afterAcceptText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Acceptance banner shown', /(پذیرفته‌اید|accepted this quotation)/.test(afterAcceptText))
  check('No more Accept/Reject buttons after accept', !/(پذیرش پیشنهاد|Accept quotation)/.test(afterAcceptText) && !/(رد پیشنهاد|Reject quotation)/.test(afterAcceptText))

  // Verify status badge updated (Accepted)
  check('Status badge updated to Accepted', /(پذیرفته شد|Accepted)/.test(afterAcceptText))

  // Close drawer
  await page.evaluate(() => {
    const btn = document.querySelector('[role="dialog"] button[aria-label*="بستن"], [role="dialog"] button[aria-label*="Close"]')
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 400))
}

// ---- 3. Reject flow ----
console.log('\n[3] Reject flow')
const rejectName = await pickByState((rec) => rec.can_respond === true)
console.log(`    candidate Sent quote: ${rejectName}`)
check('found another Sent quote to reject', !!rejectName && rejectName !== acceptName)
if (rejectName) {
  await openDrawer(rejectName)
  await clickByText(['رد پیشنهاد', 'Reject quotation'], '[role="dialog"]')
  await new Promise(r => setTimeout(r, 600))
  await snap('reject_confirm_panel', 3)

  const rejectConfirmText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Reject confirm panel appears with note textarea', /(تأیید رد|Confirm rejection)/.test(rejectConfirmText) && /(یادداشت|Optional note)/.test(rejectConfirmText))

  await reactSet('[role="dialog"] textarea', 'Phase 7B e2e: rejected because budget is tight.')
  await clickByText(['بله، رد می‌کنم', 'Yes, reject'], '[role="dialog"]')
  await new Promise(r => setTimeout(r, 2500))
  await snap('reject_after_submit', 4)

  const afterRejectText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Rejection banner shown', /(رد کرده‌اید|rejected this quotation)/.test(afterRejectText))
  check('Rejection note echoed back', afterRejectText.includes('Phase 7B e2e'))
  check('No Accept/Reject buttons after reject', !/(پذیرش پیشنهاد|Accept quotation)/.test(afterRejectText) && !/(رد پیشنهاد|Reject quotation)/.test(afterRejectText))
  check('Status badge shows Rejected', /(رد شد|Rejected)/.test(afterRejectText))

  // Refresh: response persists
  await page.reload({ waitUntil: 'load' })
  await new Promise(r => setTimeout(r, 1800))
  await openDrawer(rejectName)
  const persistText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Rejection persists after page reload', /(رد کرده‌اید|rejected this quotation)/.test(persistText) && persistText.includes('Phase 7B e2e'))
  await page.evaluate(() => {
    const btn = document.querySelector('[role="dialog"] button[aria-label*="بستن"], [role="dialog"] button[aria-label*="Close"]')
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 400))
}

// ---- 4. Draft quote shows no accept/reject ----
console.log('\n[4] Draft quote shows no Accept/Reject')
const draftName = await pickByState((rec) => rec.erpnext_quotation && (rec.quotation_status === 'Draft'))
console.log(`    candidate Draft quote: ${draftName}`)
if (draftName) {
  await openDrawer(draftName)
  await snap('draft_drawer', 5)
  const draftText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
  check('Draft shows "not finalized" hint', /(هنوز توسط تیم فروش نهایی|still being finalized)/.test(draftText))
  check('Draft has no Accept/Reject buttons', !/(پذیرش پیشنهاد|Accept quotation)/.test(draftText) && !/(رد پیشنهاد|Reject quotation)/.test(draftText))
  await page.evaluate(() => {
    const btn = document.querySelector('[role="dialog"] button[aria-label*="بستن"], [role="dialog"] button[aria-label*="Close"]')
    if (btn) btn.click()
  })
  await new Promise(r => setTimeout(r, 400))
} else {
  console.log('    no Draft quotes available -- skipping draft check')
}

// ---- 5. Drawer overflow check at multiple widths (Phase 7A.1 regression) ----
console.log('\n[5] Drawer overflow / mobile sanity')
if (acceptName) {
  await openDrawer(acceptName)
  const at1440 = await page.evaluate(() => {
    const drawer = document.querySelector('[role="dialog"][aria-modal="true"]')
    const scrollArea = drawer?.querySelector('.overflow-y-auto')
    return {
      drawerW: drawer?.clientWidth,
      scrollScrollW: scrollArea?.scrollWidth,
      scrollClientW: scrollArea?.clientWidth,
      bodyScrollW: document.body.scrollWidth,
      bodyClientW: document.body.clientWidth,
    }
  })
  check('Drawer has no horizontal overflow at 1440', (at1440.scrollScrollW || 0) <= (at1440.scrollClientW || 0) + 1)
  check('Page has no horizontal overflow at 1440', at1440.bodyScrollW <= at1440.bodyClientW + 1)

  await page.setViewport({ width: 390, height: 844 })
  await new Promise(r => setTimeout(r, 600))
  await snap('drawer_mobile_390', 6)
  const at390 = await page.evaluate(() => {
    const drawer = document.querySelector('[role="dialog"][aria-modal="true"]')
    const scrollArea = drawer?.querySelector('.overflow-y-auto')
    return {
      drawerW: drawer?.clientWidth,
      viewportW: window.innerWidth,
      scrollScrollW: scrollArea?.scrollWidth,
      scrollClientW: scrollArea?.clientWidth,
      bodyScrollW: document.body.scrollWidth,
      bodyClientW: document.body.clientWidth,
    }
  })
  check('Drawer fits within mobile viewport', at390.drawerW <= at390.viewportW)
  check('Drawer has no horizontal overflow at 390', (at390.scrollScrollW || 0) <= (at390.scrollClientW || 0) + 1)
  check('Page has no horizontal overflow at 390', at390.bodyScrollW <= at390.bodyClientW + 1)
  await page.setViewport({ width: 1440, height: 900 })
}

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
