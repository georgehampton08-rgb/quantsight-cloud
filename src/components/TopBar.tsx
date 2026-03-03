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
    const [width, setWidth] = useState(window.innerWidth);

    useEffect(() => {
        const onResize = () => setWidth(window.innerWidth);
        window.addEventListener('resize', onResize);
        return () => window.removeEventListener('resize', onResize);
    }, []);

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

    // Treat anything below 680px as "narrow" (catches DevTools-docked viewports)
    const isNarrow = width < 680;

    return (
        <>
            <div className="flex-shrink-0 sticky top-0 z-[1000] border-b border-slate-700/50 bg-slate-900/95 backdrop-blur-md">
                {/* Main bar row */}
                <div className="flex items-center h-14 px-3 gap-2 overflow-hidden">

                    {/* Left: Hamburger (narrow) or Back+Selector (wide) */}
                    {isNarrow ? (
                        <button
                            onClick={toggleMobileMenu}
                            className="flex-shrink-0 p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                            title="Menu"
                        >
                            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                        </button>
                    ) : (
                        <div className="flex-shrink-0 flex items-center gap-3">
                            <button
                                onClick={() => navigate(-1)}
                                className="p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                                title="Go Back"
                            >
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <CascadingSelector />
                        </div>
                    )}

                    {/* Center: Search bar (flex-1 so it fills available space) */}
                    <div className="flex-1 min-w-0 px-2">
                        {isNarrow ? (
                            <div className="flex-1 max-w-[160px] mx-auto">
                                <CascadingSelector />
                            </div>
                        ) : (
                            <OmniSearchBar />
                        )}
                    </div>

                    {/* Right: Status LEDs — always visible, compact on narrow */}
                    <div className="flex-shrink-0 flex items-center gap-1.5 md:gap-3">
                        <StatusLed label="NBA" status={health.nba} />
                        <StatusLed label="AI" status={health.gemini} />
                        <StatusLed label="DB" status={health.database} />
                    </div>
                </div>

                {/* Narrow: Search bar below the main row */}
                {isNarrow && (
                    <div className="px-3 pb-2">
                        <OmniSearchBar />
                    </div>
                )}
            </div>
        </>
    )
}
