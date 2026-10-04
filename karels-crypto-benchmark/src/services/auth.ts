import { getFirebase, isCloudConfigured } from './firebase'

export interface AuthUser {
  uid: string
  email: string | null
  displayName: string | null
}

const isPhone = () => typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod/i.test(navigator.userAgent)

/** Google sign-in: popup on laptop, redirect on phones (popups are unreliable there). */
export async function signInWithGoogle(): Promise<void> {
  const { auth, authMod } = await getFirebase()
  const provider = new authMod.GoogleAuthProvider()
  provider.setCustomParameters({ prompt: 'select_account' })
  const resolver = authMod.browserPopupRedirectResolver
  if (isPhone()) await authMod.signInWithRedirect(auth, provider, resolver)
  else await authMod.signInWithPopup(auth, provider, resolver)
}

export async function signOut(): Promise<void> {
  const { auth, authMod } = await getFirebase()
  await authMod.signOut(auth)
}

/** Auth state; completes a pending redirect sign-in first so the UI never flashes "signed out". */
export function onAuth(cb: (user: AuthUser | null) => void, onError?: (e: unknown) => void): () => void {
  if (!isCloudConfigured()) {
    cb(null)
    return () => {}
  }
  let unsub: (() => void) | null = null
  let cancelled = false
  void getFirebase().then(async ({ auth, authMod }) => {
    try {
      await authMod.getRedirectResult(auth, authMod.browserPopupRedirectResolver)
    } catch (e) {
      onError?.(e)
    }
    if (cancelled) return
    unsub = authMod.onAuthStateChanged(auth, (u) =>
      cb(u ? { uid: u.uid, email: u.email, displayName: u.displayName } : null),
    )
  })
  return () => {
    cancelled = true
    unsub?.()
  }
}
