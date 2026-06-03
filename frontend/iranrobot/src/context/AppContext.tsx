import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import type {
  CartLine,
  RouteName,
  WalletTx,
} from '../types'
import { loadJSON, saveJSON, uid } from '../lib/storage'

interface RouteState {
  name: RouteName
  param?: string
}

interface AppContextValue {
  // Routing
  route: RouteState
  go: (name: RouteName, param?: string) => void
  // Cart
  cart: CartLine[]
  cartOpen: boolean
  setCartOpen: (open: boolean) => void
  addToCart: (line: Omit<CartLine, 'id' | 'addedAt'>) => void
  updateCartLine: (id: string, patch: Partial<CartLine>) => void
  removeCartLine: (id: string) => void
  clearCart: () => void
  // Wallet
  walletBalanceUsd: number
  walletTxs: WalletTx[]
  topupWallet: (amountUsd: number) => void
  spendWallet: (amountUsd: number, label: string) => boolean
  // Onboarding
  onboardingSeen: boolean
  dismissOnboarding: () => void
  showOnboarding: () => void
  onboardingOpen: boolean
}

const AppContext = createContext<AppContextValue | null>(null)

const ROUTES_FROM_HASH: Record<string, RouteName> = {
  '': 'home',
  '#': 'home',
  '#/': 'home',
  '#/home': 'home',
  '#/catalog': 'catalog',
  '#/procurement': 'procurement',
  '#/rent': 'rent',
  '#/finder': 'finder',
  '#/wallet': 'wallet',
  '#/support': 'support',
  '#/account': 'account',
}

function parseHash(hash: string): RouteState {
  const robotMatch = hash.match(/^#\/robot\/(.+)$/)
  if (robotMatch) return { name: 'robot', param: decodeURIComponent(robotMatch[1]!) }

  // Phase 6 -- account sub-routes: #/account, #/account/<section>
  const accountMatch = hash.match(/^#\/account(?:\/([^/]+))?\/?$/)
  if (accountMatch) {
    const sub = accountMatch[1] ? decodeURIComponent(accountMatch[1]) : ''
    return { name: 'account', param: sub || undefined }
  }

  const key = hash || ''
  const route = ROUTES_FROM_HASH[key]
  if (route) return { name: route }
  return { name: 'home' }
}

function stringifyRoute(state: RouteState): string {
  if (state.name === 'home') return '#/'
  if (state.name === 'robot') return `#/robot/${encodeURIComponent(state.param ?? '')}`
  if (state.name === 'account') {
    return state.param ? `#/account/${encodeURIComponent(state.param)}` : '#/account'
  }
  return `#/${state.name}`
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<RouteState>(() =>
    typeof window === 'undefined' ? { name: 'home' } : parseHash(window.location.hash),
  )

  useEffect(() => {
    const onHash = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  const go = useCallback((name: RouteName, param?: string) => {
    const next = stringifyRoute({ name, param })
    if (window.location.hash !== next) {
      window.location.hash = next
    } else {
      setRoute({ name, param })
    }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])

  const [cart, setCart] = useState<CartLine[]>(() => loadJSON('cart', [] as CartLine[]))
  const [cartOpen, setCartOpen] = useState(false)

  useEffect(() => saveJSON('cart', cart), [cart])

  const addToCart: AppContextValue['addToCart'] = useCallback((line) => {
    setCart((prev) => {
      const existing = prev.find(
        (l) => l.robotId === line.robotId && l.mode === line.mode,
      )
      if (existing) {
        return prev.map((l) =>
          l.id === existing.id
            ? {
                ...l,
                qty: l.qty + line.qty,
                days: line.days ?? l.days,
                notes: line.notes ?? l.notes,
              }
            : l,
        )
      }
      return [
        ...prev,
        { ...line, id: uid('cl'), addedAt: Date.now() },
      ]
    })
    setCartOpen(true)
  }, [])

  const updateCartLine: AppContextValue['updateCartLine'] = useCallback((id, patch) => {
    setCart((prev) => prev.map((l) => (l.id === id ? { ...l, ...patch } : l)))
  }, [])

  const removeCartLine: AppContextValue['removeCartLine'] = useCallback((id) => {
    setCart((prev) => prev.filter((l) => l.id !== id))
  }, [])

  const clearCart = useCallback(() => setCart([]), [])

  const [walletBalanceUsd, setWalletBalance] = useState<number>(() =>
    loadJSON('wallet.balance', 0),
  )
  const [walletTxs, setWalletTxs] = useState<WalletTx[]>(() =>
    loadJSON('wallet.txs', [] as WalletTx[]),
  )

  useEffect(() => saveJSON('wallet.balance', walletBalanceUsd), [walletBalanceUsd])
  useEffect(() => saveJSON('wallet.txs', walletTxs), [walletTxs])

  const topupWallet = useCallback((amountUsd: number) => {
    if (amountUsd <= 0) return
    setWalletBalance((b) => b + amountUsd)
    setWalletTxs((txs) => [
      {
        id: uid('tx'),
        amountUsd,
        type: 'topup',
        label: 'افزایش موجودی کیف پول',
        at: Date.now(),
      },
      ...txs,
    ])
  }, [])

  const spendWallet = useCallback(
    (amountUsd: number, label: string) => {
      if (amountUsd <= 0) return true
      let ok = false
      setWalletBalance((b) => {
        if (b >= amountUsd) {
          ok = true
          return b - amountUsd
        }
        return b
      })
      if (ok) {
        setWalletTxs((txs) => [
          { id: uid('tx'), amountUsd, type: 'spend', label, at: Date.now() },
          ...txs,
        ])
      }
      return ok
    },
    [],
  )

  const [onboardingSeen, setOnboardingSeen] = useState<boolean>(() =>
    loadJSON('onboarding.seen', false),
  )
  const [onboardingOpen, setOnboardingOpen] = useState<boolean>(() => !onboardingSeen)

  useEffect(() => saveJSON('onboarding.seen', onboardingSeen), [onboardingSeen])

  const dismissOnboarding = useCallback(() => {
    setOnboardingSeen(true)
    setOnboardingOpen(false)
  }, [])

  const showOnboarding = useCallback(() => setOnboardingOpen(true), [])

  const value = useMemo<AppContextValue>(
    () => ({
      route,
      go,
      cart,
      cartOpen,
      setCartOpen,
      addToCart,
      updateCartLine,
      removeCartLine,
      clearCart,
      walletBalanceUsd,
      walletTxs,
      topupWallet,
      spendWallet,
      onboardingSeen,
      onboardingOpen,
      dismissOnboarding,
      showOnboarding,
    }),
    [
      route,
      go,
      cart,
      cartOpen,
      addToCart,
      updateCartLine,
      removeCartLine,
      clearCart,
      walletBalanceUsd,
      walletTxs,
      topupWallet,
      spendWallet,
      onboardingSeen,
      onboardingOpen,
      dismissOnboarding,
      showOnboarding,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components -- provider + hook colocated by design
export function useApp(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used within AppProvider')
  return ctx
}

