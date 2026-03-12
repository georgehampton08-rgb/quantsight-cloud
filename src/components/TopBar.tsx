import { useState, useEffect } from 'react'
import CascadingSelector from './common/CascadingSelector'
import OmniSearchBar from './OmniSearchBar'
import StatusLed from './common/StatusLed'
import { useHealth } from '../context/HealthContext'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft, Menu, X } from 'lucide-react'

export default function TopBar() {
    const { health } = useHealth();
    const navigate = useNavigate();
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    useEffect(() => {
        const checkSidebar = () => {
            const sidebar = document.querySelector('.sidebar');
            setMobileMenuOpen(sidebar?.classList.contains('open') || false);
        };
        checkSidebar();
        window.addEventListener('sidebarToggled', checkSidebar);
        return () => window.removeEventListener('sidebarToggled', checkSidebar);
    }, []);

    const toggleMobileMenu = () => {
        const sidebar = document.querySelector('.sidebar');
        const isOpen = sidebar?.classList.contains('open');
        if (isOpen) {
            sidebar?.classList.remove('open');
        } else {
            sidebar?.classList.add('open');
        }
        window.dispatchEvent(new Event('sidebarToggled'));
    };

    return (
        <>
            <div className="flex-shrink-0 sticky top-0 z-[1000] border-b border-pro-border bg-pro-bg shadow-[0_1px_0_0_rgba(255,255,255,0.03)]">
                {/* Main bar row */}
                <div className="flex items-center h-14 px-3 gap-2 overflow-hidden">

                    {/* Hamburger (Mobile Only) */}
                    <button
                        onClick={toggleMobileMenu}
                        className="md:hidden flex-shrink-0 p-2 rounded-sm hover:bg-white/[0.05] text-slate-400 hover:text-white transition-colors duration-100"
                        title="Menu"
                    >
                        {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                    </button>

                    {/* Back + CascadingSelector — hidden on narrow screens */}
                    <div className="hidden sm:flex items-center gap-2 flex-shrink-0">
                        <button
                            onClick={() => navigate(-1)}
                            className="p-2 rounded-sm hover:bg-white/[0.05] text-slate-400 hover:text-white transition-colors duration-100"
                            title="Go Back"
                        >
                            <ChevronLeft className="w-4 h-4" />
                        </button>
                        <CascadingSelector />
                    </div>

                    {/* CascadingSelector only — shown on narrow screens */}
                    <div className="flex sm:hidden flex-1 min-w-0">
                        <CascadingSelector />
                    </div>

                    {/* Search bar — fills remaining space, hidden on narrow, shown in row below */}
                    <div className="hidden sm:flex flex-1 min-w-0 px-2">
                        <OmniSearchBar />
                    </div>

                    {/* Status LEDs */}
                    <div className="flex-shrink-0 flex items-center gap-1.5 sm:gap-3">
                        <StatusLed label="NBA" status={health.nba} />
                        <StatusLed label="AI" status={health.gemini} />
                        <StatusLed label="DB" status={health.database} />
                    </div>
                </div>

                {/* Search bar — shown below on narrow screens */}
                <div className="sm:hidden px-3 pb-2">
                    <OmniSearchBar />
                </div>
            </div>
        </>
    )
}
