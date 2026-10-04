import type { Attempt } from '@/game/types'
import type { WordState } from '@/game/word'
import { getFirebase } from './firebase'

export type Attempts = Record<string, Attempt>
export type Unsubscribe = () => void

export interface AttemptStore {
  kind: 'local' | 'cloud'
  subscribe(cb: (attempts: Attempts) => void, onError?: (e: unknown) => void): Unsubscribe
  save(attempts: Attempt[]): Promise<void>
}

const LOCAL_KEY = 'kcb:attempts'

function readLocal(): Attempts {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) ?? '{}') as Attempts
  } catch {
    return {}
  }
}

/** Browser-only store, used when Firebase is not configured (and for the preview build). */
export class LocalStore implements AttemptStore {
  readonly kind = 'local' as const
  private listeners = new Set<(a: Attempts) => void>()
  subscribe(cb: (a: Attempts) => void): Unsubscribe {
    this.listeners.add(cb)
    cb(readLocal())
    return () => this.listeners.delete(cb)
  }
  async save(list: Attempt[]): Promise<void> {
    const all = readLocal()
    for (const a of list) all[a.clueId] = a
    try {
      localStorage.setItem(LOCAL_KEY, JSON.stringify(all))
    } catch {
      /* storage full or blocked: keep the in-memory view going */
    }
    this.listeners.forEach((l) => l(all))
  }
}

/** users/{uid}/attempts/{clueId}: one document per clue. */
export class CloudStore implements AttemptStore {
  readonly kind = 'cloud' as const
  constructor(readonly uid: string) {}

  subscribe(cb: (a: Attempts) => void, onError?: (e: unknown) => void): Unsubscribe {
    let unsub: Unsubscribe | null = null
    let cancelled = false
    void getFirebase().then(({ db, fsMod }) => {
      if (cancelled) return
      unsub = fsMod.onSnapshot(
        fsMod.collection(db, 'users', this.uid, 'attempts'),
        (snap) => {
          const all: Attempts = {}
          snap.forEach((d) => {
            all[d.id] = d.data() as Attempt
          })
          cb(all)
        },
        (e) => onError?.(e),
      )
    })
    return () => {
      cancelled = true
      unsub?.()
    }
  }

  async save(list: Attempt[]): Promise<void> {
    const { db, fsMod } = await getFirebase()
    // A batch holds at most 500 writes; a crypto has ~19 clues.
    for (let i = 0; i < list.length; i += 400) {
      const batch = fsMod.writeBatch(db)
      for (const a of list.slice(i, i + 400)) {
        batch.set(fsMod.doc(db, 'users', this.uid, 'attempts', a.clueId), a)
      }
      await batch.commit()
    }
  }
}

/** Attempts saved locally before signing in, to upload once. */
export const localAttempts = (): Attempt[] => Object.values(readLocal())
export const clearLocalAttempts = () => {
  try {
    localStorage.removeItem(LOCAL_KEY)
  } catch {
    /* ignore */
  }
}

// ---- in-progress clue (survives reloads and closing the app) ----

const DRAFT_KEY = 'kcb:draft'

export function loadDraft(clueId: string): WordState | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return null
    const { state, savedAt } = JSON.parse(raw) as { state: WordState; savedAt: number }
    if (state.clueId !== clueId || state.status !== 'playing') return null
    // The app was closed without a "hide" event: count the gap since the last save as hidden.
    return state.hiddenSince === null ? { ...state, hiddenSince: savedAt } : state
  } catch {
    return null
  }
}

export function saveDraft(state: WordState | null): void {
  try {
    if (!state || state.status !== 'playing') localStorage.removeItem(DRAFT_KEY)
    else localStorage.setItem(DRAFT_KEY, JSON.stringify({ state, savedAt: Date.now() }))
  } catch {
    /* ignore */
  }
}
