import { useState, type FormEvent } from 'react';
import { isFirebaseConfigured } from './firebaseApp';
import { useAuth } from './AuthProvider';

type Mode = 'signin' | 'signup';

function friendlyAuthError(err: unknown): string {
  const code =
    typeof err === 'object' && err && 'code' in err
      ? String((err as { code: string }).code)
      : '';
  if (code === 'auth/email-already-in-use') {
    return 'That email already has an account — use Sign in instead.';
  }
  if (code === 'auth/weak-password') {
    return 'Password must be at least 6 characters.';
  }
  if (code === 'auth/invalid-email') {
    return 'Enter a valid email address.';
  }
  if (code === 'auth/invalid-credential' || code === 'auth/wrong-password' || code === 'auth/user-not-found') {
    return 'Wrong email or password. Create an account if you are new.';
  }
  if (code === 'auth/operation-not-allowed') {
    return 'Email/Password sign-in is disabled in Firebase Console. Enable it under Authentication → Sign-in method.';
  }
  return err instanceof Error ? err.message : 'Authentication failed';
}

export function LoginPage() {
  const { signInEmail, signUpEmail, signInGoogle, error, loading } = useAuth();
  const [mode, setMode] = useState<Mode>('signup');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  if (!isFirebaseConfigured()) {
    return (
      <div className="login-shell">
        <div className="login-stage">
          <aside className="login-hero" aria-hidden="true">
            <p className="login-brand">TradeGraph</p>
            <p className="login-hero-line">Clearance workspace for evidence-backed duty decisions.</p>
          </aside>
          <div className="login-card">
            <h1>Sign-in required</h1>
            <p className="muted">
              The API has authentication enabled, but this browser app is missing Firebase web
              config. Add <code>VITE_FIREBASE_*</code> values (see docs/FIREBASE_AUTH.md) and restart
              Vite.
            </p>
          </div>
        </div>
      </div>
    );
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setLocalError(null);
    try {
      if (mode === 'signup') {
        await signUpEmail(email.trim(), password, name.trim() || undefined);
      } else {
        await signInEmail(email.trim(), password);
      }
    } catch (err) {
      setLocalError(friendlyAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const onGoogle = async () => {
    setBusy(true);
    setLocalError(null);
    try {
      await signInGoogle();
    } catch (err) {
      setLocalError(friendlyAuthError(err));
    } finally {
      setBusy(false);
    }
  };

  const isSignup = mode === 'signup';

  return (
    <div className="login-shell">
      <div className="login-stage">
        <aside className="login-hero">
          <p className="login-brand">TradeGraph</p>
          <h2 className="login-hero-title">Ship ready. Rates cited.</h2>
          <p className="login-hero-line">
            A clearance workspace for classification, duty, preferential claims, and papers — with
            sources you can check.
          </p>
        </aside>
        <div className="login-card">
        <h1>{isSignup ? 'Create account' : 'Sign in'}</h1>
        <p className="muted">
          {isSignup
            ? 'Register with email and password, or continue with Google. First-time users are provisioned automatically on the API.'
            : 'Use the email/password you registered, or continue with Google.'}
        </p>
        <div className="login-mode-toggle" role="tablist" aria-label="Auth mode">
          <button
            type="button"
            role="tab"
            aria-selected={isSignup}
            className={isSignup ? 'active' : ''}
            onClick={() => {
              setMode('signup');
              setLocalError(null);
            }}
          >
            Create account
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={!isSignup}
            className={!isSignup ? 'active' : ''}
            onClick={() => {
              setMode('signin');
              setLocalError(null);
            }}
          >
            Sign in
          </button>
        </div>
        <form className="login-form" onSubmit={onSubmit}>
          {isSignup ? (
            <label>
              Display name (optional)
              <input
                type="text"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
          ) : null}
          <label>
            Email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
            />
          </label>
          <button type="submit" className="btn-primary" disabled={busy || loading}>
            {busy
              ? isSignup
                ? 'Creating account…'
                : 'Signing in…'
              : isSignup
                ? 'Create account'
                : 'Sign in with email'}
          </button>
        </form>
        <button
          type="button"
          className="btn-secondary login-google"
          onClick={onGoogle}
          disabled={busy || loading}
        >
          Continue with Google
        </button>
        {(localError || error) && <p className="login-error">{localError || error}</p>}
        <p className="muted login-hint">
          Tip: In Firebase Console → Authentication → Sign-in method, enable Email/Password (and
          Google if you use it).
        </p>
        </div>
      </div>
    </div>
  );
}
