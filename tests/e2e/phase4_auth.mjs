import puppeteer from 'puppeteer-core'
import fs from 'node:fs'

const SHOTS = 'tests/artifacts/phase4-auth'
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

/** Set a React-controlled input value via the native setter + input event. */
async function reactSetValue(selector, value) {
  await page.evaluate((sel, val) => {
    const input = document.querySelector(sel)
    if (!input) return
    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set
    setter.call(input, val)
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }, selector, value)
}

async function getAuthState() {
  return page.evaluate(() => {
    const userMenuBtn = Array.from(document.querySelectorAll('header button[aria-haspopup="menu"]'))
      .find(b => b.querySelector('svg.lucide-user, svg[class*="lucide-user"]'))
    const loginBtn = Array.from(document.querySelectorAll('header button')).find(b => {
      const t = b.textContent?.trim() || ''
      return /^(Login|ورود)\s*$/.test(t) && b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')
    })
    const loginModal = document.querySelector('[aria-labelledby="login-title"]')
    return {
      hasUserMenu: !!userMenuBtn,
      userMenuLabel: userMenuBtn?.textContent?.trim() ?? null,
      hasLoginBtn: !!loginBtn,
      loginModalOpen: !!loginModal,
    }
  })
}

async function snap(label, n) {
  await new Promise(r => setTimeout(r, 700))
  await page.screenshot({ path: `${SHOTS}/${String(n).padStart(2,'0')}_${label}.png` })
  return getAuthState()
}

console.log('=== Phase 4 E2E (final) ===\n')

// 1. Boot, dismiss onboarding
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
let s = await snap('home_guest', 1)
const t1 = s.hasLoginBtn && !s.hasUserMenu && !s.loginModalOpen
console.log(`[1] guest boot:           login=${s.hasLoginBtn} menu=${s.hasUserMenu} modal=${s.loginModalOpen}  -> ${t1?'PASS':'FAIL'}`)

// 2. Open login
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button')) {
    if (b.querySelector('svg.lucide-log-in, svg[class*="lucide-log-in"]')) { b.click(); return }
  }
})
s = await snap('login_open', 2)
const t2 = s.loginModalOpen
console.log(`[2] login modal opens:    modal=${s.loginModalOpen}  -> ${t2?'PASS':'FAIL'}`)

// 3. Wrong password
await reactSetValue('input[type="email"]', 'customer1@example.com')
await reactSetValue('input[type="password"]', 'WRONG-PASSWORD')
await page.click('button[type="submit"]')
await new Promise(r => setTimeout(r, 1500))
const errText = await page.evaluate(() => {
  const banner = document.querySelector('[class*="bg-brand-50"][class*="border-brand-100"]')
  return banner?.textContent?.trim() ?? null
})
s = await snap('wrong_pw', 3)
const t3 = !!errText && /اشتباه|incorrect/i.test(errText) && s.loginModalOpen
console.log(`[3] wrong pw error:       "${errText}"  modal still open=${s.loginModalOpen}  -> ${t3?'PASS':'FAIL'}`)

// 4. Correct password (React setter clears reliably)
await reactSetValue('input[type="password"]', 'ChangeMe-123')
await page.click('button[type="submit"]')
await new Promise(r => setTimeout(r, 2500))
s = await snap('logged_in', 4)
const t4 = s.hasUserMenu && !s.loginModalOpen && /(Test|Customer)/i.test(s.userMenuLabel || '')
console.log(`[4] login succeeds:       menu=${s.hasUserMenu} label="${s.userMenuLabel}" modal=${s.loginModalOpen}  -> ${t4?'PASS':'FAIL'}`)

// 5. Account view
await page.evaluate(() => { window.location.hash = '#/account' })
await new Promise(r => setTimeout(r, 800))
await snap('account_view', 5)
const accountText = await page.evaluate(() => document.querySelector('main')?.textContent?.slice(0, 700) ?? '')
const t5 = /(Test Customer|Welcome|خوش)/.test(accountText) && /customer1@example\.com/i.test(accountText)
console.log(`[5] account greets+email: t5=${t5}  -> ${t5?'PASS':'FAIL'}`)

// 6. Reload -> session persists
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
s = await snap('after_reload', 6)
const t6 = s.hasUserMenu && !s.hasLoginBtn
console.log(`[6] session persists:     menu=${s.hasUserMenu} login=${s.hasLoginBtn}  -> ${t6?'PASS':'FAIL'}`)

// 7. Logout
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button[aria-haspopup="menu"]')) {
    if (b.querySelector('svg.lucide-user, svg[class*="lucide-user"]')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 500))
await page.evaluate(() => {
  for (const b of document.querySelectorAll('header button[role="menuitem"]')) {
    if (/Sign out|خروج/.test(b.textContent || '')) { b.click(); return }
  }
})
await new Promise(r => setTimeout(r, 1500))
s = await snap('after_logout', 7)
const t7 = s.hasLoginBtn && !s.hasUserMenu
console.log(`[7] logout works:         login=${s.hasLoginBtn} menu=${s.hasUserMenu}  -> ${t7?'PASS':'FAIL'}`)

// 8. Reload still guest
await page.goto('http://localhost:5173/', { waitUntil: 'load' })
await dismissOnboarding()
s = await snap('reload_guest', 8)
const t8 = s.hasLoginBtn && !s.hasUserMenu
console.log(`[8] logout persists:      login=${s.hasLoginBtn} menu=${s.hasUserMenu}  -> ${t8?'PASS':'FAIL'}`)

console.log(`\n  page errors:    ${pageErrors.length}`)
console.log(`  console errors: ${consoleErr.length}`)
pageErrors.forEach(e => console.log(`    ❌ ${e.message}`))
consoleErr.slice(0,4).forEach(m => console.log(`    [err] ${m.text.slice(0,300)}`))

const all = [t1, t2, t3, t4, t5, t6, t7, t8]
const passed = all.filter(Boolean).length
console.log(`\n${passed}/${all.length} PASSED`)

await browser.close()
console.log(`\nscreenshots: ${SHOTS}/`)
