import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';

interface MatchupRadarProps {
    playerStats: {
        scoring: number;
        playmaking: number;
        rebounding: number;
        defense: number;
        pace: number;
    };
    opponentDefense: { // Inverted scale: Higher is weaker defense (better for player)
        scoring: number;
        playmaking: number;
        rebounding: number;
        defense: number;
        pace: number;
    };
}

export default function MatchupRadar({ playerStats, opponentDefense }: MatchupRadarProps) {
    const data = [
        { subject: 'Scoring', A: playerStats.scoring, B: opponentDefense.scoring, fullMark: 100 },
        { subject: 'Playmaking', A: playerStats.playmaking, B: opponentDefense.playmaking, fullMark: 100 },
        { subject: 'Rebounding', A: playerStats.rebounding, B: opponentDefense.rebounding, fullMark: 100 },
        { subject: 'Defense', A: playerStats.defense, B: opponentDefense.defense, fullMark: 100 },
        { subject: 'Pace', A: playerStats.pace, B: opponentDefense.pace, fullMark: 100 },
    ];

    return (
        <div className="w-full aspect-square max-h-[400px] relative">
            <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="80%" data={data}>
                    <PolarGrid stroke="#334155" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />

                    {/* Player Shape (Blue) */}
                    <Radar
                        name="Player"
                        dataKey="A"
                        stroke="#64ffda"
                        strokeWidth={2}
                        fill="#64ffda"
                        fillOpacity={0.3}
                    />

                    {/* Opponent Weakness Shape (Red/Pink) */}
                    <Radar
                        name="Opponent Weakness"
                        dataKey="B"
                        stroke="#f43f5e"
                        strokeWidth={2}
                        fill="#f43f5e"
                        fillOpacity={0.2}
                    />
                </RadarChart>
            </ResponsiveContainer>

            {/* Legend Overlay */}
            <div className="absolute top-2 right-2 flex flex-col gap-1 text-[10px]">
                <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-financial-accent/50 rounded-full"></div>
                    <span className="text-slate-400">Player Strength</span>
                </div>
                <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-rose-500/50 rounded-full"></div>
                    <span className="text-slate-400">Opponent Vulnerability</span>
                </div>
            </div>
        </div>
    );
}
