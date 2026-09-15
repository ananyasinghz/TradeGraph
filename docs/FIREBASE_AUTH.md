# Firebase Authentication setup (TradeGraph)

TradeGraph uses **Firebase Authentication** for Email/Password and Google OAuth. The React app obtains a Firebase **ID token**; FastAPI verifies it via Google JWKS (no service-account JSON required for verify).

## 1. Create a Firebase project

1. Open [Firebase Console](https://console.firebase.google.com/).
2. Create a project (or use an existing one).
3. Add a **Web** app; copy the firebaseConfig values.
4. **Authentication → Sign-in method**: enable **Email/Password** and **Google**.
5. **Authentication → Settings → Authorized domains**: add `localhost` (and your production host).

## 2. Frontend env (`frontend/.env` or root Vite env)

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project-id
VITE_FIREBASE_APP_ID=1:...:web:...
VITE_FIREBASE_MESSAGING_SENDER_ID=...
```

These values are public by design (browser SDK). Protect the API with backend auth + Firebase authorized domains.

## 3. Backend env (`.env`)

```env
TRADE_AUTH_ENABLED=true
TRADE_FIREBASE_PROJECT_ID=your-project-id
# Optional invite-only allowlist (comma-separated emails). Empty = allow any verified Firebase user.
TRADE_FIREBASE_ALLOWED_EMAILS=
# First logins matching these emails become admin
TRADE_BOOTSTRAP_ADMIN_EMAILS=you@example.com
TRADE_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
```

## 4. Local demo without Firebase

Keep `TRADE_AUTH_ENABLED=false` (default for development) so existing demo Bearer tokens / open local API still work for CI and offline demos. **Production** (`TRADE_ENVIRONMENT=production`) forces auth on.

## 5. MFA

Enable MFA in the Firebase console for Google accounts if required by your org. TradeGraph does not implement a separate MFA stack.

## 6. Token flow

```text
Login (email/password or Google)
  → Firebase ID token
  → Authorization: Bearer <idToken>
  → FastAPI verifies iss/aud/exp/sub via Google securetoken JWKS
  → Upsert users row; Principal(role, organization_id)
```
