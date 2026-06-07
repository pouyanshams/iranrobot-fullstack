import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase6-dashboard'
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

async function reactSet(selector, value, isTextArea = false) {
  await page.evaluate((sel, val, isTA) => {
    const el = document.querySelector(sel)
    if (!el) return
    const proto = isTA ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype
    const setter = Object.getOwnPropertyDescriptor(proto, 'value').set
    setter.call(el, val)
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value, isTextArea)
}

async function clickByText(needles) {
  return page.evaluate((arr) => {
    for (const b of document.querySelectorAll('button')) {
      const t = (b.textContent || '').trim()
      for (const n of arr) if (t.includes(n)) { b.click(); return t }
    }
    return null
  }, needles)
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

console.log('=== Phase 6 E2E ===\n')

// 1. Guest hits /#/account -> login modal opens.
console.log('[1] Guest visit /#/account -> login modal')
await page.goto('http://localhost:5173/#/account', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 800))
await snap('guest_login_modal', 1)
const guestState = await page.evaluate(() => ({
  modal: !!document.querySelector('[aria-labelledby="login-title"]'),
  loginBtn: !!Array.from(document.querySelectorAll('header button')).find(b => /Login|ورود/.test(b.textContent||'')),
}))
check('Guest at /#/account opens login modal', guestState.modal, JSON.stringify(guestState))

// 2. Login as customer1
console.log('\n[2] Login -> Account dashboard opens')
await reactSet('input[type="email"]', 'customer1@example.com')
await reactSet('input[type="password"]', 'ChangeMe-123')
await page.click('button[type="submit"]')
await new Promise(r => setTimeout(r, 2500))
await snap('account_overview', 2)
const overviewText = await page.evaluate(() => document.querySelector('main')?.innerText?.slice(0, 800) || '')
check('Account overview shows greeting + counts',
  /Welcome|خوش/.test(overviewText) && /Quote|استعلام/.test(overviewText) && /Procurement|تأمین/.test(overviewText) && /Support|پشتیبانی/.test(overviewText),
  overviewText.slice(0, 200))

// 3. Sidebar -> Quote requests (click within aside to avoid matching header nav)
console.log('\n[3] Navigate to Quote requests via sidebar')
async function clickSidebar(needles) {
  return page.evaluate((arr) => {
    const aside = document.querySelector('aside')
    if (!aside) return null
    for (const b of aside.querySelectorAll('button')) {
      const t = (b.textContent || '').trim()
      for (const n of arr) if (t.includes(n)) { b.click(); return t }
    }
    return null
  }, needles)
}
await clickSidebar(['استعلام‌ها', 'Quote requests'])
await new Promise(r => setTimeout(r, 900))
await snap('quotes_list', 3)
const quotesText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
const hasQR = /QR-\d+-\d+/.test(quotesText)
check('Quote list shows real QR ids', hasQR, quotesText.slice(0,200))

// 4. Open first quote detail
console.log('\n[4] Open first quote -> detail drawer')
await page.evaluate(() => {
  const row = document.querySelector('main ul li button')
  if (row) row.click()
})
await new Promise(r => setTimeout(r, 1200))
await snap('quote_detail', 4)
const drawerText = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
const detailHasQr = /QR-\d+-\d+/.test(drawerText)
const detailHasItems = /Items|اقلام/.test(drawerText)
check('Quote detail drawer shows record + items', detailHasQr && detailHasItems, drawerText.slice(0,200))

// 5. Close drawer + navigate to procurement
console.log('\n[5] Navigate to Procurement')
await page.evaluate(() => {
  const btn = document.querySelector('[role="dialog"] button[aria-label]')
  if (btn) btn.click()
})
await new Promise(r => setTimeout(r, 500))
await clickSidebar(['درخواست تأمین', 'Procurement'])
await new Promise(r => setTimeout(r, 900))
await snap('procurement_list', 5)
const procText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Procurement list shows PR ids', /PR-\d+-\d+/.test(procText), procText.slice(0,200))

// 6. Open procurement detail
console.log('\n[6] Open procurement detail')
await page.evaluate(() => {
  const row = document.querySelector('main ul li button')
  if (row) row.click()
})
await new Promise(r => setTimeout(r, 1200))
await snap('procurement_detail', 6)
const procDrawer = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
check('Procurement detail drawer shows fields',
  /PR-\d+-\d+/.test(procDrawer) && /(Brand|برند|Origin|کشور|product|Requested|محصول)/.test(procDrawer),
  procDrawer.slice(0,200))

// 7. Close + go to Support
console.log('\n[7] Navigate to Support tickets')
await page.evaluate(() => {
  const btn = document.querySelector('[role="dialog"] button[aria-label]')
  if (btn) btn.click()
})
await new Promise(r => setTimeout(r, 500))
await clickSidebar(['پشتیبانی', 'Support'])
await new Promise(r => setTimeout(r, 900))
await snap('support_list', 7)
const supText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check('Support list shows ISS ids', /ISS-\d+-\d+/.test(supText), supText.slice(0,200))

// 8. Open support detail
console.log('\n[8] Open support detail')
await page.evaluate(() => {
  const row = document.querySelector('main ul li button')
  if (row) row.click()
})
await new Promise(r => setTimeout(r, 1200))
await snap('support_detail', 8)
const supDrawer = await page.evaluate(() => document.querySelector('[role="dialog"]')?.innerText || '')
check('Support detail drawer shows subject + body', /ISS-\d+-\d+/.test(supDrawer) && /(Subject|موضوع)/.test(supDrawer), supDrawer.slice(0,200))

// 9. Profile -> edit + save
console.log('\n[9] Profile edit')
await page.evaluate(() => {
  const btn = document.querySelector('[role="dialog"] button[aria-label]')
  if (btn) btn.click()
})
await new Promise(r => setTimeout(r, 500))
await clickSidebar(['پروفایل', 'Profile'])
await new Promise(r => setTimeout(r, 900))
await snap('profile_form', 9)

// Find the phone input (text input, dir="ltr", inputmode="tel")
const newPhone = `0912${String(Math.floor(1000 + Math.random()*9000))}${String(Math.floor(100 + Math.random()*900))}`
await page.evaluate((phone) => {
  const tel = document.querySelector('main input[inputmode="tel"]')
  if (!tel) return
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  setter.call(tel, phone)
  tel.dispatchEvent(new Event('input', { bubbles: true }))
}, newPhone)
// Use form submit directly to avoid any button-text ambiguity.
await page.evaluate(() => {
  const form = document.querySelector('main form')
  if (form) form.requestSubmit()
})
// Save call + whoami refresh can take ~1.5s. Poll briefly for the banner.
let sawSavedBanner = false
let bannerText = ''
for (let i = 0; i < 30; i++) {
  await new Promise(r => setTimeout(r, 200))
  bannerText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
  if (/Changes saved|تغییرات ذخیره شد/.test(bannerText)) { sawSavedBanner = true; break }
}
await snap('profile_saved', 10)
check('Profile save shows success banner', sawSavedBanner, bannerText.slice(0,300))

// 10. Hard reload -> phone persists
console.log('\n[10] Reload + check phone persisted')
await page.goto('http://localhost:5173/#/account/profile', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 1200))
await snap('profile_after_reload', 11)
const reloadedPhone = await page.evaluate(() => {
  const tel = document.querySelector('main input[inputmode="tel"]')
  return tel?.value || ''
})
check(`Phone persisted after reload (${reloadedPhone} === ${newPhone})`, reloadedPhone === newPhone)

// 11. Ownership check: try forged QR id from URL hash (no UI exposes this)
console.log('\n[11] Forged record id via direct API call -> 404 envelope')
const forged = await page.evaluate(async () => {
  const r = await fetch('/api/method/iranrobot_backend.api.requests.get_my_request_detail?kind=quote&name=QR-2026-99999', {
    credentials: 'include',
    headers: { 'Accept': 'application/json' },
  })
  const body = await r.json()
  const env = body.message || {}
  return { status: r.status, ok: env.ok, code: (env.error || {}).code }
})
check('Forged id returns NOT_FOUND (no leak)', forged.ok === false && forged.code === 'NOT_FOUND', JSON.stringify(forged))

// 12. Header still navigates
console.log('\n[12] Header navigation unaffected -> catalog')
await page.goto('http://localhost:5173/#/catalog', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 1500))
const catalogH1 = await page.evaluate(() => document.querySelector('main h1')?.textContent || '')
check('Catalog still renders for authenticated user', catalogH1.length > 0, `h1="${catalogH1}"`)

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
