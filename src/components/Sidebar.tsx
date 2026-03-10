import { NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { ChevronLeft, X } from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Home', icon: '🏠', path: '/' },
    { name: 'Player Lab', icon: '🧬', path: '/player' },
    { name: 'Matchup Engine', icon: '⚔️', path: '/matchup' },
    { name: 'The Pulse', icon: '❤️', path: '/pulse' },
    { name: 'Matchup Lab', icon: '🔬', path: '/matchup-lab' },
    { name: 'Team Central', icon: '🛡️', path: '/team' },
    { name: 'Settings', icon: '⚙️', path: '/settings' },
    { name: 'About', icon: 'ℹ️', path: '/about' },
    { name: 'Vanguard', icon: '🔒', path: '/vanguard' },
    { name: 'Injury Admin', icon: '⚕️', path: '/injury-admin' },
]

export default function Sidebar() {
    const location = useLocation();

    const closeMobileSidebar = () => {
        const sidebar = document.querySelector('.sidebar');
        sidebar?.classList.remove('open');
        window.dispatchEvent(new Event('sidebarToggled'));
    };

    return (
        <div className={`sidebar h-full border-r border-slate-700/50 bg-slate-900/95 backdrop-blur-md flex flex-col p-4 transition-all duration-300 relative`}>

            {/* Close Button - Top Right */}
            <button
                onClick={closeMobileSidebar}
                className="absolute top-4 right-4 p-2 rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors z-10"
                title="Close Menu"
            >
                <X size={20} />
            </button>

            <div className={`mb-8 flex items-center gap-2 px-2`}>
                <div className="w-8 h-8 rounded bg-financial-accent/20 flex items-center justify-center text-financial-accent font-bold">
                    Q
                </div>
                <div className="font-bold text-gray-100 tracking-wider animate-in fade-in duration-300">QUANTSIGHT</div>
            </div>

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                {NAV_ITEMS.map((item) => (
                    <NavLink
                        key={item.name}
                        to={item.path}
                        onClick={closeMobileSidebar}
                        className={({ isActive }) => {
                            // For exact matching on home, otherwise check if current path matches
                            const isCurrentPath = item.path === '/'
                                ? location.pathname === '/'
                                : location.pathname === item.path || location.pathname.startsWith(item.path + '/');

                            return `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 text-sm font-medium
                            ${isActive || isCurrentPath
                                    ? 'bg-financial-accent/10 text-financial-accent border-l-2 border-financial-accent'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border-l-2 border-transparent'}`;
                        }}
                    >
                        <span className="text-lg">{item.icon}</span>
                        <span className="whitespace-nowrap">{item.name}</span>
                    </NavLink>
                ))}
            </div>

        </div>
    )
}
