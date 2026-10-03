/**
 * Firebase bootstrap (same approach as Moe's Garden): loaded lazily, and the app runs in local
 * mode when no config is present.
 */
import type { FirebaseApp } from 'firebase/app'
import type * as AuthNs from 'firebase/auth'
import type * as FirestoreNs from 'firebase/firestore'

export interface FirebaseConfig {
  apiKey: string
  authDomain: string
  projectId: string
  appId: string
}

export function readConfig(env: Record<string, string | undefined> = import.meta.env): FirebaseConfig | null {
  const apiKey = env.VITE_FIREBASE_API_KEY
  const authDomain = env.VITE_FIREBASE_AUTH_DOMAIN
  const projectId = env.VITE_FIREBASE_PROJECT_ID
  const appId = env.VITE_FIREBASE_APP_ID
  if (!apiKey || !authDomain || !projectId || !appId) return null
  return { apiKey, authDomain, projectId, appId }
}

export const isCloudConfigured = (): boolean => readConfig() !== null

type FirebaseModules = {
  app: FirebaseApp
  auth: AuthNs.Auth
  db: FirestoreNs.Firestore
  authMod: typeof AuthNs
  fsMod: typeof FirestoreNs
}

let modules: Promise<FirebaseModules> | null = null

export function getFirebase(): Promise<FirebaseModules> {
  if (!modules) {
    modules = (async () => {
      const config = readConfig()
      if (!config) throw new Error('Firebase is not configured')
      const [{ initializeApp }, authMod, fsMod] = await Promise.all([
        import('firebase/app'),
        import('firebase/auth'),
        import('firebase/firestore'),
      ])
      const app = initializeApp(config)
      const auth = authMod.initializeAuth(app, {
        persistence: [authMod.indexedDBLocalPersistence, authMod.browserLocalPersistence],
      })
      const db = fsMod.initializeFirestore(app, {
        ignoreUndefinedProperties: true,
        localCache: fsMod.persistentLocalCache({ tabManager: fsMod.persistentMultipleTabManager() }),
      })
      return { app, auth, db, authMod, fsMod }
    })()
  }
  return modules
}
