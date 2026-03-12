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
        <div className={`sidebar h-full border-r border-cyber-border bg-cyber-bg flex flex-col p-4 transition-all duration-300 relative`}>

            {/* Close Button - Top Right */}
            <button
                onClick={closeMobileSidebar}
                className="absolute top-4 right-4 p-2 rounded-full bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors z-10"
                title="Close Menu"
            >
                <X size={20} />
            </button>

            <div className={`mb-8 flex items-center gap-2 px-2`}>
                <div className="w-8 h-8 rounded-sm border border-cyber-border flex items-center justify-center text-cyber-green font-mono font-bold">
                    {'>_'}
                </div>
                <div className="font-bold text-cyber-text font-display tracking-[0.08em] uppercase animate-in fade-in duration-300">QUANTSIGHT</div>
            </div>

            <div className="flex flex-1 flex-col gap-2 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
                {NAV_ITEMS.map((item, index) => (
                    <React.Fragment key={item.name}>
                        {/* Admin divider */}
                        {item.path === '/vanguard' && (
                            <div className="my-1 border-t border-cyber-border mt-2 pt-2" />
                        )}
                        <NavLink
                            to={item.path}
                            onClick={closeMobileSidebar}
                            className={({ isActive }) => {
                                const isCurrentPath = item.path === '/'
                                    ? location.pathname === '/'
                                    : location.pathname === item.path || location.pathname.startsWith(item.path + '/');
                                
                                const isAdmin = item.path === '/vanguard' || item.path === '/injury-admin';

                                return `flex items-center gap-3 px-3 py-2.5 rounded-sm transition-all text-xs font-display font-600 tracking-[0.08em] uppercase group
                                ${isActive || isCurrentPath
                                    ? 'bg-cyber-green/5 text-cyber-green border-l-2 border-cyber-green'
                                    : isAdmin
                                        ? 'text-cyber-muted/60 hover:text-qs-gold hover:bg-white/[0.03] border-l-2 border-transparent duration-100'
                                        : 'text-cyber-muted hover:text-cyber-text hover:bg-white/[0.03] border-l-2 border-transparent duration-100'
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
