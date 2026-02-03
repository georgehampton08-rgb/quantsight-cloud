import { useState } from 'react'
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

    return (
        <>
            <div className="h-16 border-b border-slate-700/50 bg-slate-900/20 backdrop-blur-sm flex items-center px-4 md:px-6 justify-between relative z-40 overflow-visible">
                {/* Mobile Menu Button */}
                <button
                    onClick={() => {
                        const sidebar = document.querySelector('.sidebar');
                        sidebar?.classList.toggle('open');
                        setMobileMenuOpen(!mobileMenuOpen);
                    }}
                    className="md:hidden p-2 rounded-full hover:bg-white/10 text-slate-400 hover:text-white transition-colors"
                    title="Menu"
                >
                    {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </button>

                <div className="hidden md:flex items-center gap-6 flex-1 overflow-visible">
                    {/* Back Button - Desktop */}
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

                {/* Mobile: Just show app title */}
                <div className="md:hidden flex-1 text-center">
                    <h1 className="text-lg font-bold text-white">QuantSight</h1>
                </div>

                {/* Status LEDs - Hide on mobile, show on tablet+ */}
                <div className="hidden lg:flex items-center gap-4">
                    <StatusLed label="NBA" status={health.nba} />
                    <StatusLed label="AI" status={health.gemini} />
                    <StatusLed label="DB" status={health.database} />
                </div>

                {/* Mobile: Just show a simple status dot */}
                <div className="lg:hidden">
                    <div className={`w-3 h-3 rounded-full ${health.nba === 'healthy' && health.database === 'healthy' ? 'bg-green-500' : 'bg-yellow-500'} animate-pulse`} />
                </div>
            </div>

            {/* Mobile Search - Below topbar */}
            <div className="md:hidden px-4 py-2 border-b border-slate-700/50 bg-slate-900/20">
                <OmniSearchBar />
            </div>
        </>
    )
}
