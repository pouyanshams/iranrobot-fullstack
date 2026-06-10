import { LanguageProvider } from './i18n'
import { AppProvider, useApp } from './context/AppContext'
import { AuthProvider } from './context/AuthContext'
import { Header } from './components/Header'
import { Footer } from './components/Footer'
import { QuoteDrawer } from './components/QuoteDrawer'
import { LoginModal } from './components/LoginModal'
import { ErrorBoundary } from './components/ErrorBoundary'
import { HomeView } from './views/Home'
import { CatalogView } from './views/Catalog'
import { ProcurementView } from './views/Procurement'
import { RentView } from './views/Rent'
import { FinderView } from './views/Finder'
import { WalletView } from './views/Wallet'
import { SupportView } from './views/Support'
import { RobotDetailView } from './views/RobotDetail'
import { AccountView } from './views/Account'

function RouteSwitch() {
  const { route } = useApp()
  // The route switch used to be wrapped in <AnimatePresence mode="wait"> with a
  // motion.div doing a fade transition keyed on `route.name + route.param`.
  // That triggered a full exit/enter animation cycle on every sidebar
  // subcategory click. Under React 19 + StrictMode dev double-invocation,
  // framer-motion dropped the new mount's `animate` trigger about half the
  // time, leaving the motion.div pinned at initial.opacity=0 -- the symptom
  // users saw as "products appear briefly, then the page turns white". We
  // strip the animation entirely so navigation can never get stuck invisible.
  // The individual views (CatalogView, RobotDetailView) keep their own
  // motion-driven entrance animations on their internal content.
  return (
    <>
      {route.name === 'home' ? <HomeView /> : null}
      {route.name === 'catalog' ? <CatalogView /> : null}
      {route.name === 'procurement' ? <ProcurementView /> : null}
      {route.name === 'rent' ? <RentView /> : null}
      {route.name === 'finder' ? <FinderView /> : null}
      {route.name === 'wallet' ? <WalletView /> : null}
      {route.name === 'support' ? <SupportView /> : null}
      {route.name === 'account' ? <AccountView /> : null}
      {route.name === 'robot' ? (
        <RobotDetailView slug={route.param ?? ''} />
      ) : null}
    </>
  )
}

function Shell() {
  return (
    <div className="min-h-screen flex flex-col bg-base overflow-x-clip">
      <Header />
      <main className="flex-1">
        {/* Catches any render-time exception so a child crash never leaves the
            user staring at a blank page (replaces a previously-seen "white
            screen after subcategory click" symptom with a recovery panel). */}
        <ErrorBoundary>
          <RouteSwitch />
        </ErrorBoundary>
      </main>
      <Footer />
      <QuoteDrawer />
      {/* Phase 4 -- login modal rendered at shell level so any child component
          (Header user-menu, Account view guest fallback) can open it via
          useAuth().openLogin() without prop drilling. */}
      <LoginModal />
    </div>
  )
}

export default function App() {
  return (
    <LanguageProvider>
      {/* AuthProvider sits above AppProvider so AppContext consumers can use
          useAuth() too (e.g. cart drawer once Phase 5 lands). */}
      <AuthProvider>
        <AppProvider>
          <Shell />
        </AppProvider>
      </AuthProvider>
    </LanguageProvider>
  )
}
