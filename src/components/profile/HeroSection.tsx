import { PlayerProfile } from '../../services/playerApi';

interface HeroSectionProps {
    player: PlayerProfile;
}

export default function HeroSection({ player }: HeroSectionProps) {
    return (
        <div className="relative rounded-2xl overflow-hidden bg-slate-800/20 border border-slate-700/50 mb-6">
            {/* Background with Team Colors (Pseudo-logic for now) */}
            <div className="absolute inset-0 bg-gradient-to-r from-financial-bg via-transparent to-financial-accent/10 opacity-60" />

            <div className="relative flex items-center p-8 gap-8">
                {/* Headshot */}
                <div className="relative">
                    <div className="absolute inset-0 bg-financial-accent/20 blur-2xl rounded-full" />
                    <img
                        src={player.avatar}
                        alt={player.name}
                        className="relative w-32 h-32 rounded-full border-4 border-slate-800 bg-slate-900 object-cover shadow-2xl"
                    />
                </div>

                {/* Info */}
                <div className="flex-1">
                    <div className="flex items-baseline gap-3 mb-1">
                        <h1 className="text-4xl font-bold text-white tracking-tight">{player.name}</h1>
                        <span className="text-2xl font-light text-slate-400">#{player.id}</span>
                    </div>
                    <div className="text-xl text-financial-accent font-mono mb-4">
                        {player.team} • {player.position}
                    </div>

                    {/* Vitals Grid */}
                    <div className="grid grid-cols-3 gap-12 border-t border-slate-700/50 pt-4 max-w-lg">
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Height</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.height || "N/A"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Weight</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.weight || "N/A"}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Exp</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.experience || "N/A"}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
