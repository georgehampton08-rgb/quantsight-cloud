/**
 * Firebase Authentication Service
 * =================================
 * Provides Firebase auth utilities for the QuantSight frontend.
 *
 * Sign-in is OPTIONAL for public app use.
 * Sign-in is REQUIRED only for admin/Vanguard pages.
 *
 * Having a Firebase account does NOT grant admin backend access —
 * the backend enforces a Firestore role check independently.
 */
import { initializeApp, getApps, getApp } from 'firebase/app';
import {
    getAuth,
    GoogleAuthProvider,
    signInWithRedirect,
    getRedirectResult,
    signOut,
    onAuthStateChanged,
    type User
} from 'firebase/auth';

const firebaseConfig = {
    projectId: 'quantsight-prod',
    authDomain: 'quantsight-prod.firebaseapp.com',
    // apiKey is intentionally the public Web API key (safe for frontend — it's not a secret)
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY ?? '',
};

// Singleton — avoid re-initializing across hot reloads
const _app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();

export const auth = getAuth(_app);

/**
 * Get the current user's Firebase ID token.
 * Returns null if not signed in.
 * Does NOT force-refresh — uses cached token (Firebase refreshes automatically).
 */
export const getIdToken = (): Promise<string | null> => {
    const user = auth.currentUser;
    if (!user) return Promise.resolve(null);
    return user.getIdToken(false);
};

/**
 * Attach the Firebase ID token to a fetch RequestInit object.
 * Use this for admin-gated API calls.
 */
export const withAuthHeaders = async (
    init: RequestInit = {}
): Promise<RequestInit> => {
    const token = await getIdToken();
    if (!token) throw new Error('[firebaseAuth] Not signed in. Cannot build auth headers.');
    return {
        ...init,
        headers: {
            ...(init.headers ?? {}),
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
        },
    };
};

export const signInWithGoogle = (): Promise<void> =>
    signInWithRedirect(auth, new GoogleAuthProvider());

export const signOutUser = (): Promise<void> => signOut(auth);

export { getRedirectResult, onAuthStateChanged };
export type { User };
