/**
 * Phase 4 -- Header user-menu / login button.
 *
 *   - Guest: renders a "Login" button that opens the LoginModal.
 *   - Logged in: renders a button showing the customer's name + a chevron;
 *     clicking opens a small dropdown with Account / Logout.
 *
 * Styled to match the existing header action buttons (Wallet, Cart, language
 * toggle). No layout rework.
 */

import { useEffect, useRef, useState } from 'react'
import { LogIn, LogOut, User as UserIcon, ChevronDown } from 'lucide-react'
import { useAuth } from '../lib/useAuth'
import { useApp } from '../context/AppContext'
import { useI18n } from '../i18n'

export function UserMenu() {
  const { t } = useI18n()
  const { currentUser, isAuthenticated, isLoading, openLogin, logout } = useAuth()
  const { go } = useApp()
  const [open, setOpen] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  // Close on outside click / escape.
  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (isLoading) {
    // While the boot whoami is in flight, render a quiet placeholder so the
    // header layout doesn't jump once the auth state resolves.
    return (
      <div
        className="h-10 w-24 rounded-lg bg-ink-100/60 animate-pulse"
        aria-label={t('در حال بارگذاری وضعیت ورود', 'Loading auth state')}
      />
    )
  }

  if (!isAuthenticated) {
    return (
      <button
        type="button"
        onClick={openLogin}
        className="h-10 px-4 rounded-lg text-sm font-semibold inline-flex items-center gap-2 bg-white border border-line text-fg hover:bg-ink-50 transition-colors"
      >
        <LogIn size={15} />
        <span className="hidden sm:inline">{t('ورود', 'Login')}</span>
      </button>
    )
  }

  const displayName =
    currentUser?.customer_name?.trim() ||
    currentUser?.full_name?.trim() ||
    currentUser?.email ||
    ''

  async function handleLogout() {
    setOpen(false)
    try {
      await logout()
    } catch {
      // Already handled by AuthContext; nothing the menu can do here.
    }
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="h-10 px-3 rounded-lg text-sm font-semibold inline-flex items-center gap-2 bg-white border border-line text-fg hover:bg-ink-50 transition-colors max-w-[180px]"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="grid size-6 place-items-center rounded-full bg-brand-50 text-brand-600 shrink-0">
          <UserIcon size={13} />
        </span>
        <span className="truncate">{displayName}</span>
        <ChevronDown size={13} className={['shrink-0 opacity-60 transition-transform', open ? 'rotate-180' : ''].join(' ')} />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute end-0 mt-2 w-56 rounded-xl border border-line bg-white shadow-soft-lg overflow-hidden z-50"
        >
          <div className="px-4 py-3 border-b border-line">
            <div className="text-xs text-faint">{t('ورود به عنوان', 'Signed in as')}</div>
            <div className="text-sm font-semibold text-fg truncate" dir="ltr">
              {currentUser?.email}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              go('account')
            }}
            className="w-full text-start px-4 py-2.5 text-sm hover:bg-ink-50 inline-flex items-center gap-2 text-fg"
          >
            <UserIcon size={14} className="text-ink-500" />
            {t('حساب کاربری', 'My account')}
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={handleLogout}
            className="w-full text-start px-4 py-2.5 text-sm hover:bg-ink-50 inline-flex items-center gap-2 text-brand-700"
          >
            <LogOut size={14} />
            {t('خروج', 'Sign out')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
