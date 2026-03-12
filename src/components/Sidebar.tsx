import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { ChevronLeft, X } from 'lucide-react';

import { Home, FlaskConical, Swords, Heart, Microscope, Shield, Settings, Info, Lock, Stethoscope } from 'lucide-react';

const NAV_ITEMS = [
    { name: 'Home',           Icon: Home,         path: '/' },
    { name: 'Player Lab',     Icon: FlaskConical, path: '/player' },
    { name: 'Matchup Engine', Icon: Swords,        path: '/matchup' },
    { name: 'The Pulse',      Icon: Heart,         path: '/pulse' },
    { name: 'Matchup Lab',    Icon: Microscope,    path: '/matchup-lab' },
    { name: 'Team Central',   Icon: Shield,        path: '/team' },
    { name: 'Settings',       Icon: Settings,      path: '/settings' },
    { name: 'About',          Icon: Info,          path: '/about' },
    { name: 'Vanguard',       Icon: Lock,          path: '/vanguard' },
    { name: 'Injury Admin',   Icon: Stethoscope,   path: '/injury-admin' },
]

export default function Sidebar() {
    const location = useLocation();

    const closeMobileSidebar = () => {
        const sidebar = document.querySelector('.sidebar');
        sidebar?.classList.remove('open');
        window.dispatchEvent(new Event('sidebarToggled'));
    };

    return (
        <div className={`sidebar h-full border-r border-pro-border bg-pro-bg flex flex-col p-4 transition-all duration-300 relative`}>

            {/* Close Button - Top Right (Mobile Only) */}
            <button
                onClick={closeMobileSidebar}
                className="md:hidden absolute top-4 right-4 p-2 rounded-xl bg-pro-surface border border-pro-border hover:bg-white/[0.05] text-pro-muted hover:text-pro-text transition-colors z-10"
                title="Close Menu"
            >
                <X size={20} />
            </button>

            <div className={`mb-8 flex items-center gap-2 px-2 mt-4`}>
                <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-500 font-sans font-bold text-sm">
                    QS
                </div>
                <div className="font-bold text-pro-text text-lg tracking-tight">QuantSight</div>
            </div>

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto scrollbar-premium pr-2">
                {NAV_ITEMS.map((item, index) => (
                    <React.Fragment key={item.name}>
                        {/* Admin divider */}
                        {item.path === '/vanguard' && (
                            <div className="my-1 border-t border-pro-border/50 mt-2 pt-2" />
                        )}
                        <NavLink
                            to={item.path}
                            onClick={closeMobileSidebar}
                            className={({ isActive }) => {
                                const isCurrentPath = item.path === '/'
                                    ? location.pathname === '/'
                                    : location.pathname === item.path || location.pathname.startsWith(item.path + '/');

                                const isAdmin = item.path === '/vanguard' || item.path === '/injury-admin';

                                return `flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all text-sm font-medium group
                                ${isActive || isCurrentPath
                                    ? 'bg-emerald-500/5 text-emerald-500 border-l-2 border-emerald-500'
                                    : isAdmin
                                        ? 'text-red-500/60 hover:text-red-500 hover:bg-red-500/5 border-l-2 border-transparent duration-100'
                                        : 'text-pro-muted hover:text-pro-text hover:bg-white/[0.03] border-l-2 border-transparent duration-100'
                                }`;
                            }}
                        >
                            <item.Icon className="w-4 h-4 flex-shrink-0" />
                            <span className="whitespace-nowrap">{item.name}</span>
                        </NavLink>
                    </React.Fragment>
                ))}
            </div>

        </div>
    )
}
