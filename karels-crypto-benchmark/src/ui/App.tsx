import { useEffect, useMemo, useState } from 'react'
import { isCloudConfigured } from '@/services/firebase'
import { onAuth, signInWithGoogle, type AuthUser } from '@/services/auth'
import { CloudStore, LocalStore } from '@/services/store'
import { Game } from './Game'
import { Logo } from './Logo'

export function App() {
  const cloud = isCloudConfigured()
  const [user, setUser] = useState<AuthUser | null | undefined>(cloud ? undefined : null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => onAuth(setUser, (e) => setError(String(e))), [])

  const store = useMemo(() => (user ? new CloudStore(user.uid) : cloud ? null : new LocalStore()), [user, cloud])

  if (user === undefined) {
    return (
      <div className="app">
        <div className="center">
          <Logo />
        </div>
      </div>
    )
  }
  if (!store) {
    return (
      <div className="app">
        <div className="center">
          <Logo />
          <h1>Karel's Crypto benchmark</h1>
          <p>One clue at a time. Every keystroke and revealed letter is timed and saved to your account.</p>
          <button
            className="primary"
            onClick={() => signInWithGoogle().catch((e: unknown) => setError(String(e)))}
          >
            Sign in with Google
          </button>
          {error && <div className="note">{error}</div>}
        </div>
      </div>
    )
  }
  return <Game key={store.kind + (user?.uid ?? '')} store={store} user={user} />
}
