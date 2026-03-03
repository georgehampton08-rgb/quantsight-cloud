/**
 * Auth Context (Redirect Flow)
 * ==============================
 * Uses signInWithRedirect — no popups, works everywhere, never blocked.
 *
 * Flow:
 *   1. User clicks "Sign in with Google" → redirected to Google
 *   2. Google redirects back to app
 *   3. On mount, getRedirectResult() resolves with the user
 *   4. onAuthStateChanged also fires after redirect completes
 *
 * FAIL-SAFE: If Firebase init errors, user=null and app still renders.
 */
import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User } from 'firebase/auth';

interface AuthContextType {
    user: User | null | undefined;
    loading: boolean;
}

const AuthContext = createContext<AuthContextType>({ user: undefined, loading: true });

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null | undefined>(undefined);
    const [ready, setReady] = useState(false);

    useEffect(() => {
        let unsubscribe: (() => void) | undefined;

        (async () => {
            try {
                const { auth, onAuthStateChanged, getRedirectResult } = await import('../services/firebaseAuth');

                // Handle post-redirect sign-in first
                try {
                    const result = await getRedirectResult(auth);
                    if (result?.user) {
                        console.log('[AuthContext] Redirect sign-in complete:', result.user.email);
                    }
                } catch (redirectErr) {
                    console.warn('[AuthContext] getRedirectResult error (non-fatal):', redirectErr);
                }

                // Then subscribe to ongoing auth state
                unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
                    if (firebaseUser) {
                        // Sanitize: reject users without uid or unverified email
                        if (!firebaseUser.uid || !firebaseUser.emailVerified) {
                            console.warn('[AuthContext] User failed sanitization:', {
                                hasUid: !!firebaseUser.uid,
                                emailVerified: firebaseUser.emailVerified,
                                email: firebaseUser.email,
                            });
                            // Sign them out — unverified accounts have no admin access
                            import('../services/firebaseAuth').then(({ signOutUser }) => {
                                signOutUser().catch(() => { });
                            });
                            setUser(null);
                        } else {
                            setUser(firebaseUser);
                        }
                    } else {
                        setUser(null);
                    }
                    setReady(true);
                });

            } catch (err) {
                console.warn('[AuthContext] Firebase not available, admin features disabled:', err);
                setUser(null);
                setReady(true);
            }
        })();

        return () => { unsubscribe?.(); };
    }, []);

    // Safety: if Firebase never responds within 5s, fallback to null
    useEffect(() => {
        if (!ready) {
            const timeout = setTimeout(() => {
                setUser(prev => prev === undefined ? null : prev);
                setReady(true);
            }, 5000);
            return () => clearTimeout(timeout);
        }
    }, [ready]);

    return (
        <AuthContext.Provider value={{ user, loading: !ready }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = (): AuthContextType => {
    const ctx = useContext(AuthContext);
    if (ctx === undefined) {
        throw new Error('useAuth must be used inside <AuthProvider>');
    }
    return ctx;
};
