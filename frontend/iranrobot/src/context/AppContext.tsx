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

  // Phase 8C: legacy localStorage wallet (`wallet.balance`, `wallet.txs`,
  // topupWallet, spendWallet) was removed. The wallet is now backend-backed
  // via `src/api/wallet.ts` + `src/lib/useWallet.ts`. Stale localStorage keys
  // from previous releases are simply ignored -- no read or write happens
  // here. A future phase may add a one-shot cleanup if needed.

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

