import { PlayerProfile } from '../../services/playerApi';

interface HeroSectionProps {
    player: PlayerProfile;
}

export default function HeroSection({ player }: HeroSectionProps) {
    return (
        <div className="relative rounded-2xl overflow-hidden bg-slate-800/20 border border-slate-700/50 mb-6">
            {/* Background with Team Colors (Pseudo-logic for now) */}
            <div className="absolute inset-0 bg-gradient-to-r from-financial-bg via-transparent to-financial-accent/10 opacity-60" />

            <div className="relative flex flex-col sm:flex-row items-center p-6 sm:p-8 gap-6 sm:gap-8">
                {/* Headshot */}
                <div className="relative">
                    <div className="absolute inset-0 bg-financial-accent/20 blur-2xl rounded-full" />
                    <img
                        src={player.avatar}
                        alt={player.name}
                        className="relative w-24 h-24 sm:w-32 sm:h-32 rounded-full border-4 border-slate-800 bg-slate-900 object-cover shadow-2xl"
                    />
                </div>

                {/* Info */}
                <div className="flex-1 flex flex-col items-center sm:items-start text-center sm:text-left w-full">
                    <div className="flex items-baseline gap-2 sm:gap-3 mb-1">
                        <h1 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">{player.name}</h1>
                        <span className="text-xl sm:text-2xl font-light text-slate-400">#{player.id}</span>
                    </div>
                    <div className="text-lg sm:text-xl text-financial-accent font-mono mb-6 pb-4 sm:pb-0 sm:mb-4 border-b border-slate-700/50 sm:border-0 w-full sm:w-auto">
                        {player.team} • {player.position}
                    </div>

                    {/* Vitals Grid */}
                    <div className="grid grid-cols-3 gap-4 sm:gap-12 sm:border-t border-slate-700/50 sm:pt-4 w-full max-w-lg">
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Height</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.height}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Weight</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.weight}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Exp</div>
                            <div className="font-semibold text-slate-200 text-lg">{player.experience}</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
