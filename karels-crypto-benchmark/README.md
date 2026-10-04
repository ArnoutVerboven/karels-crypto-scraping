# karels-crypto-benchmark

A phone-first webapp for the **human solver benchmark** (ROADMAP #1, issue #9): one clue at a
time, oldest crypto first, with every keystroke and revealed letter timed and stored per clue.
It replaces the `human_benchmark_worksheet.csv` flow.

- **Clue screen**: type with the on-screen keyboard (or a laptop keyboard). When every cell is
  filled the guess is checked: green and on to the next clue, or red and everything stays in
  place (no penalty). *Show letter* fills a missing/wrong letter (in a random order fixed by a per-clue seed) and locks it; if that
  completes the word, the clue counts as failed. *Skip clue* / *Skip crypto* for clues whose
  solution you've already seen.
- **Menu**: browse all cryptos and clues (never the solutions) with solved / failed / skipped
  status and date. Skipped and unplayed clues can be opened from there. Download/copy all data
  as JSON.
- Opening the app shows the oldest clue that is not solved, failed or skipped; after finishing
  or skipping a clue it continues with the next open clue after it (wrapping around).
- The clock pauses while the app is in the background or the menu is open; an unfinished clue
  survives a reload.

Clues come from `karels-crypto-scraping/data/history.json` and
`karels-crypto-solving/data/ingested_puzzles.json` (only words with a known solution), built
into `src/data/clues.json` by `scripts/build-clues.mjs` on every build. The deploy workflow
re-runs after each weekly scrape, so new cryptos appear automatically.

## What is recorded

One Firestore document per clue at `users/{uid}/attempts/{clueId}` (`src/game/types.ts`):

| field | meaning |
| --- | --- |
| `outcome` | `solved`, `failed` or `skipped` (`skipReason`: `clue` / `crypto`) |
| `length`, `lettersNeeded`, `revealedCount` | letters in the answer, letters you had to find (length − revealed), letters shown |
| `activeMs`, `wallMs`, `firstKeyMs` | time on the clue (background time excluded), wall-clock time, time to first keystroke |
| `letterMs[i]` | active ms when position *i* got its final typed letter (`null` if shown) |
| `wrongGuesses`, `reveals` | each wrong full guess and each *Show letter*, with time |
| `events` | the full timeline: every type / delete / reveal / submit / hide / show |
| `completedByReveal` | failed because *Show letter* filled the last missing letter |
| `seed`, `revealOrder` | seed of the *Show letter* order and the answer positions it gives (from v2). Each *Show letter* reveals the first position in `revealOrder` that is still empty or wrong, so an LLM run can be shown the same letters; `revealOrderFor(answer, seed)` in `src/game/word.ts` regenerates the order |

## Run locally

```bash
pnpm install
pnpm dev        # local mode: attempts stay in this browser
pnpm check      # typecheck + tests
```

Without Firebase config the app runs in local mode (browser storage). Attempts made in local
mode are uploaded the first time you sign in on that device.

## Firebase setup (one-time)

Same setup as Moe's Garden, on the free Spark plan:

1. <https://console.firebase.google.com> → **Add project** (e.g. `karels-crypto`), no Analytics.
2. **Build → Authentication → Sign-in method → Google → Enable**.
3. **Build → Firestore Database → Create database**, `europe-west1`, production mode.
4. **Project settings → General → Your apps → Web app** (no hosting checkbox needed): copy the
   config into `karels-crypto-benchmark/.env.production` (see `.env.example`). Set
   `VITE_FIREBASE_AUTH_DOMAIN=<project-id>.web.app` so sign-in works on phones, and add
   `https://<project-id>.web.app` + `https://<project-id>.web.app/__/auth/handler` to the
   OAuth web client in Google Cloud console → APIs & Services → Credentials.
5. **Project settings → Service accounts → Generate new private key**. In GitHub → Settings →
   Secrets and variables → Actions: secret `FIREBASE_SERVICE_ACCOUNT` = the JSON, variable
   `FIREBASE_PROJECT_ID` = the project id. Give the service account the **Firebase Rules Admin**
   role (Google Cloud console → IAM) so CI can publish `firestore.rules`.

`.github/workflows/benchmark-app.yml` then deploys `main` to `https://<project-id>.web.app`
and every PR to a preview channel. Until configured it only runs the checks.
