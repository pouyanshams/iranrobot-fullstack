/**
 * Phase 8C E2E -- backend-backed wallet UI.
 *
 * Pre-requisite: run the bench fixture once so we have an isolated user with
 * a seeded Approved Top Up (so transaction history isn't empty):
 *
 *   bench --site iranrobot.localhost execute \
 *     iranrobot_backend.commands._phase8c_e2e_fixtures.seed_phase8c_e2e_fixture
 *
 * That writes `tests/artifacts/phase8c_e2e_fixture.json` which this suite reads.
 */

import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase8c-wallet'
fs.rmSync(SHOTS, { recursive: true, force: true })
fs.mkdirSync(SHOTS, { recursive: true })

const FIX_PATH = 'tests/artifacts/phase8c_e2e_fixture.json'
if (!fs.existsSync(FIX_PATH)) {
  console.error(`MISSING FIXTURE: ${FIX_PATH}`)
  console.error('Run: bench --site iranrobot.localhost execute iranrobot_backend.commands._phase8c_e2e_fixtures.seed_phase8c_e2e_fixture')
  process.exit(1)
}
const FIX = JSON.parse(fs.readFileSync(FIX_PATH, 'utf-8'))

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

// The UI renders numbers in Persian digits (۰-۹) when the locale is fa.
// Normalize before regex-matching so assertions don't depend on locale.
const PERSIAN_DIGIT_MAP = { '۰':'0','۱':'1','۲':'2','۳':'3','۴':'4','۵':'5','۶':'6','۷':'7','۸':'8','۹':'9','٠':'0','١':'1','٢':'2','٣':'3','٤':'4','٥':'5','٦':'6','٧':'7','٨':'8','٩':'9' }
function ascii(s) {
  return String(s || '').replace(/[۰-۹٠-٩]/g, (c) => PERSIAN_DIGIT_MAP[c] || c)
}

const PASS = []
const FAIL = []
function check(label, ok, extra = '') {
  if (ok) { PASS.push(label); console.log(`  ✅ ${label}`) }
  else { FAIL.push(label); console.log(`  ❌ ${label} ${extra}`) }
}

console.log('=== Phase 8C E2E -- backend-backed wallet ===\n')
console.log(`  fixture: ${FIX.email}  wallet=${FIX.wallet}  seeded balance=$${FIX.seeded_balance_usd}`)

// ---------------------------------------------------------------- [1] guest #/wallet
console.log('\n[1] guest visiting #/wallet sees login-required panel')
await page.goto('http://localhost:5173/#/wallet', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 1200))
await snap('guest_wallet', 1)
const guestMainText = await page.evaluate(() => document.querySelector('main')?.innerText || '')
check(
  'guest wallet page shows Log in panel',
  /(برای استفاده از کیف پول وارد شوید|Log in to use your wallet)/.test(guestMainText),
  `text=${guestMainText.slice(0, 200)}`,
)
check(
  'guest wallet page does NOT show numeric balance',
  !/\$\s?\d+\.\d{2}/.test(guestMainText),
)

// ---------------------------------------------------------------- [2] login as fixture user
console.log('\n[2] log in as the fixture customer')
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
await reactSet('[aria-labelledby="login-title"] input[type="email"]', FIX.email)
await reactSet('[aria-labelledby="login-title"] input[type="password"]', FIX.password)
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2500))
await snap('logged_in_home', 2)

// Capture LS snapshot to confirm later that we never wrote wallet.balance / wallet.txs.
const lsBefore = await page.evaluate(() =>
  Object.keys(localStorage).filter((k) => k.toLowerCase().includes('wallet')),
)
check(
  'no wallet localStorage keys set after fresh signup login',
  lsBefore.length === 0,
  `found=${JSON.stringify(lsBefore)}`,
)

// ---------------------------------------------------------------- [3] Header has Wallet link, no balance
console.log('\n[3] Header shows Wallet link without numeric balance')
const headerText = await page.evaluate(() => document.querySelector('header')?.innerText || '')
check('Header shows Wallet label', /(کیف پول|Wallet)/.test(headerText))
check(
  'Header does NOT show a numeric $ balance',
  !/\$\s?\d/.test(headerText),
  `header=${headerText.slice(0, 300)}`,
)

// ---------------------------------------------------------------- [4] #/wallet redirects authenticated users
console.log('\n[4] authenticated #/wallet redirects to #/account/wallet')
await page.goto('http://localhost:5173/#/wallet', { waitUntil: 'load' })
await new Promise(r => setTimeout(r, 1500))
const hashAfter = await page.evaluate(() => window.location.hash)
check(
  'authenticated #/wallet hash becomes #/account/wallet',
  hashAfter === '#/account/wallet' || hashAfter.startsWith('#/account/wallet'),
  `hash=${hashAfter}`,
)
await snap('account_wallet_after_redirect', 3)

// ---------------------------------------------------------------- [5] Account sidebar Wallet entry
console.log('\n[5] Account sidebar lists Wallet entry')
const sidebarText = await page.evaluate(() => document.querySelector('aside')?.innerText || '')
check('Wallet entry in sidebar', /(کیف پول|Wallet)/.test(sidebarText), `sidebar=${sidebarText.slice(0, 200)}`)

// ---------------------------------------------------------------- [6] balance card renders backend balance
console.log('\n[6] balance card shows the seeded backend balance')
await new Promise(r => setTimeout(r, 1500))
const balanceText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-balance"]')?.textContent || '',
)
check(
  'balance card contains seeded balance ($120)',
  /120/.test(ascii(balanceText)),
  `balance=${balanceText}`,
)

// ---------------------------------------------------------------- [7] transaction history shows the seeded Top Up
console.log('\n[7] transaction history shows the seeded Top Up')
const txListText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-tx-list"]')?.innerText || '',
)
check('transaction list visible', txListText.length > 0)
check('seeded transaction (WT- id) referenced in history mono refs or row', /(\+|Top Up|افزایش)/.test(txListText), `tx=${txListText.slice(0, 200)}`)
check(
  'seeded approved top-up WTR id appears in history meta',
  txListText.includes(FIX.seeded_approved_topup_request),
  `expected=${FIX.seeded_approved_topup_request} got=${txListText.slice(0, 200)}`,
)

// ---------------------------------------------------------------- [8] create a Pending top-up
console.log('\n[8] create a new Pending top-up via the form')
// Type 300 into the amount input
const amountInputSelector = 'input[placeholder*="مثلاً"], input[placeholder*="e.g."]'
await page.waitForSelector(amountInputSelector, { timeout: 4000 })
await reactSet(amountInputSelector, '300')

// Submit
await page.evaluate(() => {
  const btn = document.querySelector('[data-testid="wallet-topup-submit"]')
  if (btn) btn.click()
})
await new Promise(r => setTimeout(r, 1500))
await snap('after_submit', 4)

// Instructions banner with WTR- reference
const instructionsText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-topup-instructions"]')?.innerText || '',
)
check('success instructions banner is shown', instructionsText.length > 0, `banner=${instructionsText.slice(0, 200)}`)
check('banner contains a WTR- reference', /WTR-/.test(instructionsText))
const newRequestId = (instructionsText.match(/WTR-[A-Z0-9-]+/) || [null])[0]

// ---------------------------------------------------------------- [9] Pending row appears
console.log('\n[9] Pending row appears in pending list')
const pendingText = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pending-list"]')?.innerText || '',
)
check('pending list contains new request', newRequestId && pendingText.includes(newRequestId), `pending=${pendingText.slice(0, 200)}`)
check('pending list shows amount $300', /300/.test(ascii(pendingText)))

// Balance unchanged
const balanceAfterCreate = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-balance"]')?.textContent || '',
)
const balanceAfterCreateAscii = ascii(balanceAfterCreate)
check(
  'balance is still $120 after creating a Pending (Pending does not credit)',
  /120/.test(balanceAfterCreateAscii) && !/300|420/.test(balanceAfterCreateAscii),
  `balance=${balanceAfterCreate}`,
)

// ---------------------------------------------------------------- [10] persistence across hard refresh
console.log('\n[10] Pending request persists after hard refresh')
await page.reload({ waitUntil: 'load' })
await new Promise(r => setTimeout(r, 2000))
await snap('after_reload', 5)
const pendingAfterReload = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pending-list"]')?.innerText || '',
)
check(
  'Pending row still visible after reload (backend persistence)',
  newRequestId && pendingAfterReload.includes(newRequestId),
)

// ---------------------------------------------------------------- [11] cancel the Pending top-up
console.log('\n[11] cancel the Pending top-up')
page.on('dialog', async (d) => { await d.accept() })  // accept window.confirm
await page.evaluate((reqId) => {
  for (const row of document.querySelectorAll('[data-testid="wallet-pending-row"]')) {
    if (row.getAttribute('data-request-id') === reqId) {
      const btn = row.querySelector('[data-testid="wallet-pending-cancel"]')
      if (btn) btn.click()
      return
    }
  }
}, newRequestId)
await new Promise(r => setTimeout(r, 1800))
await snap('after_cancel', 6)
const pendingAfterCancel = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pending-list"]')?.innerText || '',
)
const pendingEmptyAfterCancel = await page.evaluate(() =>
  document.querySelector('[data-testid="wallet-pending-empty"]')?.innerText || '',
)
check(
  'Pending row gone after cancel',
  !pendingAfterCancel.includes(newRequestId) || pendingEmptyAfterCancel.length > 0,
  `pending=${pendingAfterCancel.slice(0, 200)} empty=${pendingEmptyAfterCancel.slice(0, 80)}`,
)

// ---------------------------------------------------------------- [12] localStorage never touched
console.log('\n[12] localStorage has no wallet.balance / wallet.txs writes')
const lsAfter = await page.evaluate(() =>
  Object.keys(localStorage).filter(
    (k) => k.toLowerCase().includes('wallet.balance') || k.toLowerCase().includes('wallet.txs'),
  ),
)
check(
  'no iranrobot.v1.wallet.balance or .txs in localStorage after full UI flow',
  lsAfter.length === 0,
  `found=${JSON.stringify(lsAfter)}`,
)

// ---------------------------------------------------------------- summary
console.log('')
console.log(`  page errors:    ${pageErrors.length}`)
console.log(`  console errors: ${consoleErr.length}`)
pageErrors.forEach(e => console.log(`    ❌ ${e.message}`))
consoleErr.slice(0, 4).forEach(m => console.log(`    [err] ${m.text.slice(0, 300)}`))

console.log('')
console.log(`${PASS.length}/${PASS.length + FAIL.length} PASSED`)

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
process.exit(FAIL.length === 0 ? 0 : 1)
