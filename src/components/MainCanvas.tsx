import { Routes, Route, Navigate } from 'react-router-dom'
import CommandCenterPage from '../pages/CommandCenterPage'
import PlayerProfilePage from '../pages/PlayerProfilePage'
import MatchupEnginePage from '../pages/MatchupEnginePage'
import MatchupLabPage from '../pages/MatchupLabPage'
import TeamCentralPage from '../pages/TeamCentralPage'
import SettingsPage from '../pages/SettingsPage'
import InjuryAdmin from '../pages/InjuryAdmin'

export default function MainCanvas() {
    return (
        <main className="flex-1 overflow-auto bg-slate-900/50 relative">
            {/* Background elements (grid, particles) could go here */}
            <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-5 pointer-events-none"></div>

            <Routes>
                <Route path="/" element={<CommandCenterPage />} />
                <Route path="/player" element={<PlayerProfilePage />} />
                <Route path="/player/:id" element={<PlayerProfilePage />} />
                <Route path="/matchup" element={<MatchupEnginePage />} />
                <Route path="/matchup-lab" element={<MatchupLabPage />} />
                <Route path="/team" element={<TeamCentralPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route path="/injury-admin" element={<InjuryAdmin />} />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </main>
    )
}
