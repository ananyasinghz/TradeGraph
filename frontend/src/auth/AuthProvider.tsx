import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  GoogleAuthProvider,
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updateProfile,
  type User,
} from 'firebase/auth';
import { api, setAccessTokenProvider, type AuthWhoAmI } from '../services/api';
import { getFirebaseAuth, isFirebaseConfigured } from './firebaseApp';

interface AuthContextValue {
  loading: boolean;
  firebaseUser: User | null;
  whoami: AuthWhoAmI | null;
  authRequired: boolean;
  error: string | null;
  signInEmail: (email: string, password: string) => Promise<void>;
  signUpEmail: (email: string, password: string, displayName?: string) => Promise<void>;
  signInGoogle: () => Promise<void>;
  logout: () => Promise<void>;
  refreshWhoAmI: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [whoami, setWhoami] = useState<AuthWhoAmI | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshWhoAmI = useCallback(async () => {
    try {
      const me = await api.getWhoAmI();
      setWhoami(me);
      setAuthRequired(me.auth_enabled);
      setError(null);
    } catch (err) {
      setWhoami(null);
      setError(err instanceof Error ? err.message : 'Could not load session');
    }
  }, []);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    let cancelled = false;

    const attachProvider = (user: User | null) => {
      setAccessTokenProvider(async (forceRefresh = false) => {
        if (!user) return null;
        return user.getIdToken(forceRefresh);
      });
    };

    const boot = async () => {
      let requiresAuth = false;
      try {
        const me = await api.getWhoAmI();
        if (cancelled) return;
        setWhoami(me);
        requiresAuth = me.auth_enabled;
        setAuthRequired(requiresAuth);
        if (!requiresAuth) {
          setLoading(false);
          return;
        }
      } catch {
        // Unauthenticated probe under locked API — require login.
        requiresAuth = true;
        if (!cancelled) setAuthRequired(true);
      }

      if (!isFirebaseConfigured()) {
        if (!cancelled) setLoading(false);
        return;
      }

      const auth = getFirebaseAuth();
      unsub = onAuthStateChanged(auth, async (user) => {
        if (cancelled) return;
        setFirebaseUser(user);
        attachProvider(user);
        if (user) {
          try {
            const me = await api.getWhoAmI();
            if (!cancelled) {
              setWhoami(me);
              setAuthRequired(me.auth_enabled);
              setError(null);
            }
          } catch (err) {
            if (!cancelled) {
              setWhoami(null);
              setError(err instanceof Error ? err.message : 'Session rejected by API');
            }
          }
        } else if (requiresAuth) {
          setWhoami({
            authenticated: false,
            auth_enabled: true,
            actor: 'anonymous',
            role: 'viewer',
            email: null,
            organization_id: null,
            auth_method: 'none',
          });
        }
        if (!cancelled) setLoading(false);
      });
    };

    void boot();
    return () => {
      cancelled = true;
      unsub?.();
    };
  }, []);

  const signInEmail = useCallback(async (email: string, password: string) => {
    setError(null);
    await signInWithEmailAndPassword(getFirebaseAuth(), email, password);
  }, []);

  const signUpEmail = useCallback(
    async (email: string, password: string, displayName?: string) => {
      setError(null);
      const cred = await createUserWithEmailAndPassword(
        getFirebaseAuth(),
        email,
        password,
      );
      const name = (displayName || '').trim();
      if (name) {
        await updateProfile(cred.user, { displayName: name });
      }
    },
    [],
  );

  const signInGoogle = useCallback(async () => {
    setError(null);
    await signInWithPopup(getFirebaseAuth(), new GoogleAuthProvider());
  }, []);

  const logout = useCallback(async () => {
    if (isFirebaseConfigured()) {
      await signOut(getFirebaseAuth());
    }
    setFirebaseUser(null);
    setAccessTokenProvider(async () => null);
    try {
      const me = await api.getWhoAmI();
      setWhoami(me);
      setAuthRequired(me.auth_enabled);
    } catch {
      setWhoami({
        authenticated: false,
        auth_enabled: true,
        actor: 'anonymous',
        role: 'viewer',
        email: null,
        organization_id: null,
        auth_method: 'none',
      });
      setAuthRequired(true);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      loading,
      firebaseUser,
      whoami,
      authRequired,
      error,
      signInEmail,
      signUpEmail,
      signInGoogle,
      logout,
      refreshWhoAmI,
    }),
    [
      loading,
      firebaseUser,
      whoami,
      authRequired,
      error,
      signInEmail,
      signUpEmail,
      signInGoogle,
      logout,
      refreshWhoAmI,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
