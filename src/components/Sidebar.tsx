import { NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Home', icon: '🏠', path: '/' },
    { name: 'Player Lab', icon: '🧬', path: '/player' },
    { name: 'Matchup Engine', icon: '⚔️', path: '/matchup' },
    { name: 'The Pulse', icon: '❤️', path: '/pulse' },
    { name: 'Matchup Lab', icon: '🔬', path: '/matchup-lab' },
    { name: 'Team Central', icon: '🛡️', path: '/team' },
    { name: 'Settings', icon: '⚙️', path: '/settings' },
    { name: 'Injury Admin', icon: '⚕️', path: '/injury-admin' },
]

export default function Sidebar() {
    const [collapsed, setCollapsed] = useState(false);
    const location = useLocation();

    return (
        <div className={`sidebar ${collapsed ? 'w-20' : 'w-64'} h-full border-r border-slate-700/50 bg-slate-900/30 backdrop-blur-md flex flex-col p-4 transition-all duration-300 relative`}>

            {/* Collapse Toggle */}
            <button
                onClick={() => setCollapsed(!collapsed)}
                className="absolute -right-3 top-8 bg-slate-800 border border-slate-600 rounded-full p-1 text-slate-400 hover:text-white"
            >
                {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
            </button>

            <div className={`mb-8 flex items-center gap-2 px-2 ${collapsed ? 'justify-center' : ''}`}>
                <div className="w-8 h-8 rounded bg-financial-accent/20 flex items-center justify-center text-financial-accent font-bold">
                    Q
                </div>
                {!collapsed && <div className="font-bold text-gray-100 tracking-wider animate-in fade-in duration-300">QUANTSIGHT</div>}
            </div>

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                {NAV_ITEMS.map((item) => (
                    <NavLink
                        key={item.name}
                        to={item.path}
                        className={({ isActive }) => {
                            // For exact matching on home, otherwise check if current path matches
                            const isCurrentPath = item.path === '/'
                                ? location.pathname === '/'
                                : location.pathname === item.path || location.pathname.startsWith(item.path + '/');

                            return `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 text-sm font-medium
                            ${isActive || isCurrentPath
                                    ? 'bg-financial-accent/10 text-financial-accent border-l-2 border-financial-accent'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border-l-2 border-transparent'}
                            ${collapsed ? 'justify-center px-2' : ''}`;
                        }}
                    >
                        <span className="text-lg">{item.icon}</span>
                        {!collapsed && <span className="whitespace-nowrap">{item.name}</span>}
                    </NavLink>
                ))}
            </div>

        </div>
    )
}
