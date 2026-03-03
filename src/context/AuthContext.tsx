/**
 * Auth Context
 * ============
 * Provides global auth state without forcing sign-in.
 * Public app use is unaffected — user is null when not signed in.
 * Admin Vanguard pages use AdminGuard to conditionally gate access.
 */
import React, { createContext, useContext, useEffect, useState } from 'react';
import { auth, onAuthStateChanged, type User } from '../services/firebaseAuth';

interface AuthContextType {
    /** undefined = still loading, null = not signed in, User = signed in */
    user: User | null | undefined;
    /** true only during initial auth state resolution */
    loading: boolean;
}

const AuthContext = createContext<AuthContextType>({ user: undefined, loading: true });

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null | undefined>(undefined);

    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, (firebaseUser) => {
            setUser(firebaseUser);
        });
        return unsubscribe;
    }, []);

    return (
        <AuthContext.Provider value={{ user, loading: user === undefined }}>
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
