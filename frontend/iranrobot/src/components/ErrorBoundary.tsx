import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'
import { ApiError } from './ApiState'

/**
 * Root-level error boundary. Without this, any render exception in a child
 * component would unmount the entire app and leave the user staring at a
 * blank page. We instead show a recovery panel with a "Try again" button.
 *
 * Logs to console so dev / error-reporting tooling can pick the trace up.
 */

interface State {
  error: Error | null
}

interface Props {
  children: ReactNode
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Keep the stack visible in dev so we can find the source of any render crash.
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  reset = () => {
    this.setState({ error: null })
  }

  render() {
    if (this.state.error) {
      return (
        <div className="min-h-screen flex items-center justify-center px-4 py-10 bg-base">
          <ApiError error={this.state.error} onRetry={this.reset} />
        </div>
      )
    }
    return this.props.children
  }
}
