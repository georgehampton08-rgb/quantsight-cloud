/**
 * Auth Context
 * ============
 * Provides global auth state without forcing sign-in.
 * Public app use is unaffected — user is null when not signed in.
 * Admin Vanguard pages use AdminGuard to conditionally gate access.
 *
 * FAIL-SAFE: If Firebase is not configured (missing VITE_FIREBASE_API_KEY),
 * this provider still renders children with user=null. The app works normally —
 * admin features just require Firebase to be configured.
 */
import React, { createContext, useContext, useEffect, useState } from 'react';

interface AuthContextType {
    /** undefined = still loading, null = not signed in, User = signed in */
    user: any | null | undefined;
    /** true only during initial auth state resolution */
    loading: boolean;
}

const AuthContext = createContext<AuthContextType>({ user: undefined, loading: true });

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<any | null | undefined>(undefined);
    const [ready, setReady] = useState(false);

    useEffect(() => {
        let unsubscribe: (() => void) | undefined;
        try {
            // Dynamic import so Firebase config errors don't crash module evaluation
            const { auth, onAuthStateChanged } = require('../services/firebaseAuth');
            unsubscribe = onAuthStateChanged(auth, (firebaseUser: any) => {
                setUser(firebaseUser);
                setReady(true);
            });
        } catch (err) {
            // Firebase not configured — degrade gracefully, app still works
            console.warn('[AuthProvider] Firebase auth not available, admin features disabled:', err);
            setUser(null);
            setReady(true);
        }
        return () => { unsubscribe?.(); };
    }, []);

    // If we haven't heard from Firebase yet, but we've been waiting > 3s, assume no auth
    useEffect(() => {
        if (!ready) {
            const timeout = setTimeout(() => {
                setUser(prev => prev === undefined ? null : prev);
                setReady(true);
            }, 3000);
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
