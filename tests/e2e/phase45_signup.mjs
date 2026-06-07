import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase45-signup'
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
function check(label, ok, extra = '') {
  if (ok) { PASS.push(label); console.log(`  ✅ ${label}`) }
  else { FAIL.push(label); console.log(`  ❌ ${label} ${extra}`) }
}

console.log('=== Phase 4.5 E2E ===\n')

// 1. Open Login modal as guest
console.log('[1] Open Login modal as guest')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 500))
await snap('login_modal', 1)
const modalOpen = await page.evaluate(() => !!document.querySelector('[aria-labelledby="login-title"]'))
check('Login modal opens', modalOpen)

// 2. Switch to "Create account" tab
console.log('\n[2] Switch to Create account tab')
await clickByText(['ساخت حساب', 'Create account'], '[aria-labelledby="login-title"]')
await new Promise(r => setTimeout(r, 400))
await snap('signup_tab', 2)
const sawSignupHeader = await page.evaluate(() => {
  const h = document.querySelector('[aria-labelledby="login-title"] h2')
  return !!h && /(ساخت حساب|Create your IranRobot)/.test(h.textContent || '')
})
check('Signup tab activated', sawSignupHeader)

// 3. Submit weak password -> client-side validation
console.log('\n[3] Weak password -> client-side error')
await page.evaluate(() => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  const root = document.querySelector('[aria-labelledby="login-title"]')
  const inputs = root.querySelectorAll('input')
  // Inputs in render order: first_name, last_name, email, phone, password, confirm
  const fill = (i, val) => { setter.call(inputs[i], val); inputs[i].dispatchEvent(new Event('input', { bubbles: true })) }
  fill(0, 'E2E')
  fill(1, 'Tester')
  fill(2, `e2e_signup_${Date.now()}@example.com`)
  fill(3, '0912 555 1234')
  fill(4, '123')      // weak
  fill(5, '123')
})
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 500))
const weakErrText = await page.evaluate(() => {
  const banner = document.querySelector('[aria-labelledby="login-title"] [class*="bg-brand-50"][class*="border-brand-100"]')
  return banner?.textContent?.trim() || ''
})
check('Weak password error surfaced', /حداقل|at least|8/.test(weakErrText), `banner="${weakErrText}"`)

// 4. Submit mismatched password (skip server, client catches it)
console.log('\n[4] Mismatched password -> client error')
await page.evaluate(() => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  const root = document.querySelector('[aria-labelledby="login-title"]')
  const inputs = root.querySelectorAll('input')
  setter.call(inputs[4], 'GoodPassword-123'); inputs[4].dispatchEvent(new Event('input', { bubbles: true }))
  setter.call(inputs[5], 'DifferentPassword-456'); inputs[5].dispatchEvent(new Event('input', { bubbles: true }))
})
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 500))
const mismatchText = await page.evaluate(() => {
  const banner = document.querySelector('[aria-labelledby="login-title"] [class*="bg-brand-50"][class*="border-brand-100"]')
  return banner?.textContent?.trim() || ''
})
check('Mismatch error surfaced', /یکسان|match/.test(mismatchText), `banner="${mismatchText}"`)

// 5. Submit valid signup -> auto-login
console.log('\n[5] Valid signup -> auto-login')
const UNIQUE_EMAIL = `e2e_signup_${Date.now()}@example.com`
await page.evaluate((email) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  const root = document.querySelector('[aria-labelledby="login-title"]')
  const inputs = root.querySelectorAll('input')
  setter.call(inputs[2], email); inputs[2].dispatchEvent(new Event('input', { bubbles: true }))
  setter.call(inputs[4], 'ChangeMe-123'); inputs[4].dispatchEvent(new Event('input', { bubbles: true }))
  setter.call(inputs[5], 'ChangeMe-123'); inputs[5].dispatchEvent(new Event('input', { bubbles: true }))
}, UNIQUE_EMAIL)
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 3500))
await snap('after_signup', 5)
const afterSignup = await page.evaluate(() => ({
  modal: !!document.querySelector('[aria-labelledby="login-title"]'),
  userMenu: !!Array.from(document.querySelectorAll('header button[aria-haspopup="menu"]'))
    .find(b => b.querySelector('svg.lucide-user, svg[class*="lucide-user"]')),
}))
check('Modal closes after signup', !afterSignup.modal)
check('User menu shows after auto-login', afterSignup.userMenu)

// 6. Account dashboard reachable
console.log('\n[6] /#/account dashboard opens')
await page.goto('http://localhost:5173/#/account', { waitUntil: 'load' })
await dismissOnboarding()
await new Promise(r => setTimeout(r, 1200))
const dashText = await page.evaluate(() => document.querySelector('main')?.innerText?.slice(0, 600) || '')
check('Account dashboard renders', /(Welcome|خوش|Overview|نمای کلی)/.test(dashText) && dashText.includes(UNIQUE_EMAIL), dashText.slice(0,200))

// 7. Logout + try duplicate signup
console.log('\n[7] Logout + duplicate email signup -> error')
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
// Open user menu and click sign out
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button[aria-haspopup="menu"]')) {
    if (b.querySelector('svg.lucide-user, svg[class*="lucide-user"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 400))
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button[role="menuitem"]')) {
    if (/خروج|Sign out/.test(b.textContent || '')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 1500))

await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 400))
await clickByText(['ساخت حساب', 'Create account'], '[aria-labelledby="login-title"]')
await new Promise(r => setTimeout(r, 400))
await page.evaluate((email) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
  const root = document.querySelector('[aria-labelledby="login-title"]')
  const inputs = root.querySelectorAll('input')
  const fill = (i, val) => { setter.call(inputs[i], val); inputs[i].dispatchEvent(new Event('input', { bubbles: true })) }
  fill(0, 'Dup')
  fill(2, email)
  fill(4, 'ChangeMe-123')
  fill(5, 'ChangeMe-123')
}, UNIQUE_EMAIL)
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2000))
await snap('duplicate_email', 7)
const dupErrText = await page.evaluate(() => {
  const banner = document.querySelector('[aria-labelledby="login-title"] [class*="bg-brand-50"][class*="border-brand-100"]')
  return banner?.textContent?.trim() || ''
})
check('Duplicate email rejected with clean error', /قبلاً|exists|already/.test(dupErrText), `banner="${dupErrText}"`)

// 8. Switch to login tab and sign in with the same account
console.log('\n[8] Switch to Login and sign in')
await clickByText(['ورود', 'Login'], '[aria-labelledby="login-title"]')
await new Promise(r => setTimeout(r, 400))
await reactSet('input[type="email"]', UNIQUE_EMAIL)
await reactSet('input[type="password"]', 'ChangeMe-123')
await page.evaluate(() => {
  const form = document.querySelector('[aria-labelledby="login-title"] form')
  if (form) form.requestSubmit()
})
await new Promise(r => setTimeout(r, 2500))
const reLoggedIn = await page.evaluate(() => !!Array.from(document.querySelectorAll('header button[aria-haspopup="menu"]'))
  .find(b => b.querySelector('svg.lucide-user, svg[class*="lucide-user"]')))
check('Re-login with the same account works', reLoggedIn)

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
