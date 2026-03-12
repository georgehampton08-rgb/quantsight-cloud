import { Routes, Route, Navigate } from 'react-router-dom'
import { AdminGuard } from './auth/AdminGuard'
import CommandCenterPage from '../pages/CommandCenterPage'
import PlayerProfilePage from '../pages/PlayerProfilePage'
import MatchupEnginePage from '../pages/MatchupEnginePage'
import MatchupLabPage from '../pages/MatchupLabPage'
import TeamCentralPage from '../pages/TeamCentralPage'
import SettingsPage from '../pages/SettingsPage'
import InjuryAdmin from '../pages/InjuryAdmin'
import PulsePage from '../pages/PulsePage'
import VanguardControlRoom from '../pages/VanguardControlRoom'
import BoxScoresPage from '../pages/BoxScoresPage'
import AboutPage from '../pages/AboutPage'

export default function MainCanvas() {
    return (
        <main className="flex-1 min-h-0 flex flex-col bg-pro-bg relative overflow-y-auto">
            <div className="flex-1 min-h-0 w-full relative z-10">
                <Routes>
                    <Route path="/" element={<CommandCenterPage />} />
                    <Route path="/player" element={<PlayerProfilePage />} />
                    <Route path="/player/:id" element={<PlayerProfilePage />} />
                    <Route path="/matchup" element={<MatchupEnginePage />} />
                    <Route path="/matchup-lab" element={<MatchupLabPage />} />
                    <Route path="/team" element={<TeamCentralPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/pulse" element={<PulsePage />} />
                    <Route path="/box-scores" element={<BoxScoresPage />} />
                    <Route path="/boxscores" element={<BoxScoresPage />} />
                    <Route path="/boxscores/:date" element={<BoxScoresPage />} />
                    <Route path="/about" element={<AboutPage />} />

                    {/* Admin-gated routes — show Sign In prompt when not authenticated */}
                    <Route path="/vanguard" element={
                        <AdminGuard><VanguardControlRoom /></AdminGuard>
                    } />
                    <Route path="/injury-admin" element={
                        <AdminGuard><InjuryAdmin /></AdminGuard>
                    } />

                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </div>
        </main>
    )
}
