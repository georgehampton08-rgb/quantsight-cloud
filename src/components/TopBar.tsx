import CascadingSelector from './common/CascadingSelector'
import OmniSearchBar from './OmniSearchBar'
import StatusLed from './common/StatusLed'
import { useHealth } from '../context/HealthContext'
import { useNavigate } from 'react-router-dom'
import { ChevronLeft } from 'lucide-react'

export default function TopBar() {
    const { health } = useHealth();
    const navigate = useNavigate();

    return (
        <div className="h-16 border-b border-slate-700/50 bg-slate-900/20 backdrop-blur-sm flex items-center px-6 justify-between relative z-40 overflow-visible">
            <div className="flex items-center gap-6 flex-1 overflow-visible">
                {/* Back Button */}
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

            <div className="flex items-center gap-6">
                <StatusLed label="NBA Data" status={health.nba} />
                <StatusLed label="Gemini AI" status={health.gemini} />
                <StatusLed label="Database" status={health.database} />
            </div>
        </div>
    )
}
