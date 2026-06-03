/**
 * Phase 4 + 4.5 -- Login + Signup modal.
 *
 * Single Modal with two tabs:
 *   - "Login"          -> useAuth().login(email, password)
 *   - "Create account" -> useAuth().signup(...)   (Phase 4.5)
 *
 * The actual API calls live in AuthContext; this component only owns form
 * state + presentation. On successful login OR auto-logged-in signup, the
 * AuthContext closes the modal automatically. If the signup endpoint returns
 * "account created but auto-login didn't fire", we surface a banner and flip
 * back to the Login tab with the email prefilled so the user can finish.
 */

import { useState } from 'react'
import type { FormEvent } from 'react'
import { Eye, EyeOff, LogIn, UserPlus } from 'lucide-react'
import { Modal } from './Modal'
import { Input } from './Input'
import { Button } from './Button'
import { useAuth } from '../lib/useAuth'
import { useI18n } from '../i18n'
import { FrappeApiError } from '../lib/frappeApi'

type Tab = 'login' | 'signup'

const MIN_PW = 8

export function LoginModal() {
  const { loginOpen, closeLogin, login, signup } = useAuth()
  const { t } = useI18n()

  const [tab, setTab] = useState<Tab>('login')

  // --- Login state ---
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  // --- Signup state ---
  const [suFirst, setSuFirst] = useState('')
  const [suLast, setSuLast] = useState('')
  const [suEmail, setSuEmail] = useState('')
  const [suPhone, setSuPhone] = useState('')
  const [suPw, setSuPw] = useState('')
  const [suPw2, setSuPw2] = useState('')
  const [suShowPw, setSuShowPw] = useState(false)

  function resetAll() {
    setEmail('')
    setPassword('')
    setShowPw(false)
    setBusy(false)
    setErr(null)
    setNotice(null)
    setSuFirst('')
    setSuLast('')
    setSuEmail('')
    setSuPhone('')
    setSuPw('')
    setSuPw2('')
    setSuShowPw(false)
    setTab('login')
  }

  function handleClose() {
    if (busy) return
    resetAll()
    closeLogin()
  }

  function switchTab(next: Tab) {
    if (busy) return
    setErr(null)
    setNotice(null)
    setTab(next)
  }

  // --------------------------------------------------------------------
  // Login
  // --------------------------------------------------------------------

  async function handleLogin(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setNotice(null)
    if (!email || !password) {
      setErr(t('ایمیل و رمز عبور را وارد کنید.', 'Enter your email and password.'))
      return
    }
    setBusy(true)
    try {
      await login(email.trim(), password)
      resetAll()
    } catch (e) {
      setErr(formatLoginError(e, t))
    } finally {
      setBusy(false)
    }
  }

  // --------------------------------------------------------------------
  // Signup
  // --------------------------------------------------------------------

  async function handleSignup(e: FormEvent) {
    e.preventDefault()
    setErr(null)
    setNotice(null)

    if (!suFirst.trim()) {
      setErr(t('نام را وارد کنید.', 'Please enter your first name.'))
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(suEmail.trim())) {
      setErr(t('ایمیل معتبر وارد کنید.', 'Please enter a valid email.'))
      return
    }
    if (suPw.length < MIN_PW) {
      setErr(t(`رمز عبور باید حداقل ${MIN_PW} کاراکتر باشد.`, `Password must be at least ${MIN_PW} characters.`))
      return
    }
    if (suPw !== suPw2) {
      setErr(t('رمز عبور و تأیید آن یکسان نیستند.', 'Passwords do not match.'))
      return
    }

    setBusy(true)
    try {
      const result = await signup({
        email: suEmail.trim(),
        password: suPw,
        confirm_password: suPw2,
        first_name: suFirst.trim(),
        last_name: suLast.trim() || undefined,
        phone: suPhone.trim() || undefined,
      })
      if (result.autoLoggedIn) {
        // AuthContext already closed the modal. resetAll for safety on re-open.
        resetAll()
        return
      }
      // Account was created but the auto-login round-trip didn't fire.
      // Flip to Login tab with the email prefilled.
      setEmail(result.email)
      setPassword('')
      setTab('login')
      setNotice(t('حساب شما ساخته شد. لطفاً وارد شوید.', 'Account created. Please sign in.'))
    } catch (e) {
      setErr(formatSignupError(e, t))
    } finally {
      setBusy(false)
    }
  }

  // --------------------------------------------------------------------
  // Render
  // --------------------------------------------------------------------

  const isSignup = tab === 'signup'

  return (
    <Modal open={loginOpen} onClose={handleClose} size="sm">
      <div className="p-6 sm:p-8" aria-labelledby="login-title">
        <div className="text-center">
          <div className="mx-auto grid size-12 place-items-center rounded-2xl bg-brand-50 ring-1 ring-brand-100 text-brand-600">
            {isSignup ? <UserPlus size={22} /> : <LogIn size={22} />}
          </div>
          <h2 id="login-title" className="mt-4 text-2xl font-extrabold text-fg">
            {isSignup
              ? t('ساخت حساب در ایران‌ربات', 'Create your IranRobot account')
              : t('ورود به ایران‌ربات', 'Sign in to IranRobot')}
          </h2>
          <p className="mt-2 text-sm text-muted leading-7">
            {isSignup
              ? t(
                  'با ساخت حساب، می‌توانید درخواست‌های خود را پیگیری کنید.',
                  'Create an account to track your requests.',
                )
              : t(
                  'با ورود به حساب می‌توانید درخواست‌های قبلی خود را پیگیری کنید.',
                  'Sign in to track your previous quote and procurement requests.',
                )}
          </p>
        </div>

        <Tabs tab={tab} onChange={switchTab} busy={busy} />

        {notice ? (
          <div className="mt-4 rounded-lg bg-emerald-50 border border-emerald-100 px-4 py-3 text-sm text-emerald-700">
            {notice}
          </div>
        ) : null}

        {tab === 'login' ? (
          <form onSubmit={handleLogin} className="mt-5 grid gap-4">
            <Input
              label={t('ایمیل', 'Email')}
              type="email"
              name="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={busy}
              required
            />
            <Input
              label={t('رمز عبور', 'Password')}
              type={showPw ? 'text' : 'password'}
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
              required
              trailing={
                <button
                  type="button"
                  onClick={() => setShowPw((s) => !s)}
                  className="text-faint hover:text-fg transition-colors p-1 rounded"
                  aria-label={showPw ? t('پنهان کردن رمز', 'Hide password') : t('نمایش رمز', 'Show password')}
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />

            {err ? <ErrorBanner message={err} /> : null}

            <div className="mt-2 flex flex-col sm:flex-row-reverse gap-3">
              <Button type="submit" size="lg" fullWidth disabled={busy}>
                {busy ? t('در حال ورود…', 'Signing in…') : t('ورود', 'Sign in')}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="lg"
                fullWidth
                onClick={handleClose}
                disabled={busy}
              >
                {t('انصراف', 'Cancel')}
              </Button>
            </div>

            <p className="mt-1 text-center text-xs text-faint leading-6">
              {t('حسابی ندارید؟', "Don't have an account?")}{' '}
              <button
                type="button"
                onClick={() => switchTab('signup')}
                disabled={busy}
                className="font-bold text-brand-700 hover:underline disabled:opacity-50"
              >
                {t('ساخت حساب', 'Create one')}
              </button>
            </p>
          </form>
        ) : (
          <form onSubmit={handleSignup} className="mt-5 grid gap-4">
            <div className="grid sm:grid-cols-2 gap-4">
              <Input
                label={t('نام', 'First name')}
                name="first_name"
                autoComplete="given-name"
                value={suFirst}
                onChange={(e) => setSuFirst(e.target.value)}
                disabled={busy}
                required
              />
              <Input
                label={t('نام خانوادگی (اختیاری)', 'Last name (optional)')}
                name="last_name"
                autoComplete="family-name"
                value={suLast}
                onChange={(e) => setSuLast(e.target.value)}
                disabled={busy}
              />
            </div>
            <Input
              label={t('ایمیل', 'Email')}
              type="email"
              name="email"
              autoComplete="email"
              value={suEmail}
              onChange={(e) => setSuEmail(e.target.value)}
              placeholder="you@example.com"
              disabled={busy}
              required
            />
            <Input
              label={t('شماره تماس (اختیاری)', 'Phone (optional)')}
              type="tel"
              name="phone"
              autoComplete="tel"
              dir="ltr"
              inputMode="tel"
              value={suPhone}
              onChange={(e) => setSuPhone(e.target.value)}
              placeholder="09xx xxx xxxx"
              disabled={busy}
            />
            <Input
              label={t('رمز عبور', 'Password')}
              type={suShowPw ? 'text' : 'password'}
              name="new_password"
              autoComplete="new-password"
              value={suPw}
              onChange={(e) => setSuPw(e.target.value)}
              disabled={busy}
              required
              hint={t(`حداقل ${MIN_PW} کاراکتر`, `At least ${MIN_PW} characters`)}
              trailing={
                <button
                  type="button"
                  onClick={() => setSuShowPw((s) => !s)}
                  className="text-faint hover:text-fg transition-colors p-1 rounded"
                  aria-label={suShowPw ? t('پنهان کردن رمز', 'Hide password') : t('نمایش رمز', 'Show password')}
                  tabIndex={-1}
                >
                  {suShowPw ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />
            <Input
              label={t('تکرار رمز عبور', 'Confirm password')}
              type={suShowPw ? 'text' : 'password'}
              name="confirm_password"
              autoComplete="new-password"
              value={suPw2}
              onChange={(e) => setSuPw2(e.target.value)}
              disabled={busy}
              required
            />

            {err ? <ErrorBanner message={err} /> : null}

            <div className="mt-2 flex flex-col sm:flex-row-reverse gap-3">
              <Button type="submit" size="lg" fullWidth disabled={busy}>
                {busy ? t('در حال ساخت حساب…', 'Creating account…') : t('ساخت حساب', 'Create account')}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="lg"
                fullWidth
                onClick={handleClose}
                disabled={busy}
              >
                {t('انصراف', 'Cancel')}
              </Button>
            </div>

            <p className="mt-1 text-center text-xs text-faint leading-6">
              {t('قبلاً ثبت‌نام کرده‌اید؟', 'Already have an account?')}{' '}
              <button
                type="button"
                onClick={() => switchTab('login')}
                disabled={busy}
                className="font-bold text-brand-700 hover:underline disabled:opacity-50"
              >
                {t('وارد شوید', 'Sign in')}
              </button>
            </p>
          </form>
        )}
      </div>
    </Modal>
  )
}

function Tabs({ tab, onChange, busy }: { tab: Tab; onChange: (t: Tab) => void; busy: boolean }) {
  const { t } = useI18n()
  return (
    <div className="mt-6 flex items-center bg-soft border border-line rounded-xl p-1" role="tablist">
      <TabButton active={tab === 'login'} disabled={busy} onClick={() => onChange('login')}>
        {t('ورود', 'Login')}
      </TabButton>
      <TabButton active={tab === 'signup'} disabled={busy} onClick={() => onChange('signup')}>
        {t('ساخت حساب', 'Create account')}
      </TabButton>
    </div>
  )
}

function TabButton({
  active,
  disabled,
  onClick,
  children,
}: {
  active: boolean
  disabled: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      disabled={disabled}
      className={[
        'flex-1 h-9 text-sm font-bold rounded-lg transition-all',
        active ? 'bg-white text-brand-700 shadow-soft' : 'text-muted hover:text-fg',
        disabled ? 'opacity-50 cursor-not-allowed' : '',
      ].join(' ')}
    >
      {children}
    </button>
  )
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-lg bg-brand-50 border border-brand-100 px-4 py-3 text-sm text-brand-700">
      {message}
    </div>
  )
}

function formatLoginError(e: unknown, t: (fa: string, en: string) => string): string {
  if (e instanceof FrappeApiError) {
    if (e.code === 'INVALID_CREDENTIALS') {
      return t('ایمیل یا رمز عبور اشتباه است.', 'Email or password is incorrect.')
    }
    if (e.code === 'RATE_LIMITED') {
      return t('تعداد تلاش‌های ورود زیاد است. کمی صبر کنید.', 'Too many attempts. Please wait a moment.')
    }
    if (e.code === 'VALIDATION_ERROR') {
      return e.message
    }
    if (e.code === 'NETWORK_ERROR') {
      return t('سرور در دسترس نیست. اتصال خود را بررسی کنید.', 'Server unreachable. Check your connection.')
    }
    return e.message || t('خطایی رخ داد. دوباره تلاش کنید.', 'Something went wrong. Please try again.')
  }
  return t('خطایی رخ داد. دوباره تلاش کنید.', 'Something went wrong. Please try again.')
}

function formatSignupError(e: unknown, t: (fa: string, en: string) => string): string {
  if (e instanceof FrappeApiError) {
    if (e.code === 'EMAIL_ALREADY_EXISTS') {
      return t('این ایمیل قبلاً ثبت شده است.', 'An account with this email already exists.')
    }
    if (e.code === 'PASSWORD_TOO_SHORT') {
      return e.message || t(`رمز عبور باید حداقل ${MIN_PW} کاراکتر باشد.`, `Password must be at least ${MIN_PW} characters.`)
    }
    if (e.code === 'PASSWORD_MISMATCH') {
      return t('رمز عبور و تأیید آن یکسان نیستند.', 'Passwords do not match.')
    }
    if (e.code === 'VALIDATION_ERROR') {
      return e.message
    }
    if (e.code === 'NETWORK_ERROR') {
      return t('سرور در دسترس نیست. اتصال خود را بررسی کنید.', 'Server unreachable. Check your connection.')
    }
    return e.message || t('ساخت حساب با خطا مواجه شد.', 'Could not create your account.')
  }
  return t('ساخت حساب با خطا مواجه شد.', 'Could not create your account.')
}
