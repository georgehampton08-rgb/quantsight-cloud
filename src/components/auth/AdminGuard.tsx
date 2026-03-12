/**
 * AdminGuard Component
 * ====================
 * Wraps any admin-only UI. Shows a sign-in prompt if not authenticated.
 * Already-signed-in non-admin users will see an "Access Denied" message
 * if the backend returns 403 (role not in Firestore admins collection).
 *
 * Usage:
 *   <AdminGuard>
 *     <VanguardControlRoom />
 *   </AdminGuard>
 */
import React from 'react';
import { Shield, LogIn } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { signInWithGoogle, signOutUser } from '../../services/firebaseAuth';

interface AdminGuardProps {
    children: React.ReactNode;
}

export const AdminGuard: React.FC<AdminGuardProps> = ({ children }) => {
    const { user, loading } = useAuth();

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full text-slate-400 text-sm gap-2">
                <span className="animate-spin inline-block w-4 h-4 border-2 border-slate-500 border-t-emerald-400 rounded-full" />
                Checking credentials...
            </div>
        );
    }

    if (!user) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-6 p-8">
                <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30">
                    <Shield className="w-8 h-8 text-emerald-500" />
                </div>
                <div className="text-center max-w-sm">
                    <h3 className="text-white font-bold text-xl mb-2">Admin Access Required</h3>
                    <p className="text-slate-400 text-sm leading-relaxed">
                        This area is restricted to authorized administrators.
                        Sign in with your authorized Google account to continue.
                    </p>
                    <p className="text-slate-500 text-xs mt-2">
                        Creating an account alone does not grant access.
                    </p>
                </div>
                <button
                    onClick={() => signInWithGoogle().catch((e) => console.error('[AdminGuard] Sign-in failed:', e))}
                    className="flex items-center gap-2 px-6 py-3 bg-emerald-500 text-black font-bold rounded-lg hover:bg-emerald-400 active:scale-95 transition-all shadow-lg shadow-emerald-500/20"
                >
                    <LogIn className="w-4 h-4" />
                    Sign in with Google
                </button>
            </div>
        );
    }

    // User is signed in — render children
    // The backend (require_admin_role) will return 403 if their uid
    // is not in the Firestore admins collection
    return <>{children}</>;
};

/**
 * Minimal auth status bar — renders current user email and sign-out button.
 * Embed in Vanguard control headers to show who is authenticated.
 */
export const AdminAuthBar: React.FC = () => {
    const { user } = useAuth();
    if (!user) return null;

    return (
        <div className="flex items-center gap-3 text-xs text-slate-400">
            <Shield className="w-3 h-3 text-emerald-500" />
            <span>{user.email}</span>
            <button
                onClick={() => signOutUser()}
                className="text-slate-500 hover:text-red-400 transition-colors underline"
            >
                Sign out
            </button>
        </div>
    );
};
