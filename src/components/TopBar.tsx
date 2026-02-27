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
        // Initial check
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
            <div className="h-16 border-b border-slate-700/50 bg-slate-900/20 backdrop-blur-sm flex items-center px-4 md:px-6 justify-between relative z-[1000] overflow-visible">
                {/* Mobile Menu Button */}
                <button
                    onClick={toggleMobileMenu}
                    className="md:hidden p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                    title="Menu"
                >
                    {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>

                {/* Desktop: Back Button + Full Layout */}
                <div className="hidden md:flex items-center gap-6 flex-1 overflow-visible">
                    <button
                        onClick={() => navigate(-1)}
                        className="p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                        title="Go Back"
                    >
                        <ChevronLeft className="w-5 h-5" />
                    </button>
                    <CascadingSelector />
                    <div className="flex-1">
                        <OmniSearchBar />
                    </div>
                </div>

                {/* Mobile: Compact Select Context + Title */}
                <div className="md:hidden flex-1 flex items-center justify-center gap-2 px-2">
                    <div className="flex-1 max-w-[200px]">
                        <CascadingSelector />
                    </div>
                </div>

                {/* Status LEDs - Always visible */}
                <div className="flex items-center gap-2 md:gap-4">
                    <StatusLed label="NBA" status={health.nba} />
                    <StatusLed label="AI" status={health.gemini} />
                    <StatusLed label="DB" status={health.database} />
                </div>
            </div>

            {/* Mobile Search - Below topbar */}
            <div className="md:hidden px-4 py-2 border-b border-slate-700/50 bg-slate-900/20">
                <OmniSearchBar />
            </div>
        </>
    )
}
