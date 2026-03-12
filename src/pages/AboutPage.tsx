/**
 * About Page — /#/about
 * ======================
 * Static informational page describing the QuantSight Cloud platform.
 * Follows the same layout, spacing, and styling conventions as
 * SettingsPage.tsx (the closest structural match).
 *
 * No data fetching — fully static content.
 */


export default function AboutPage() {
    return (
        <div className="h-full w-full overflow-y-auto bg-pro-bg border-x border-pro-border flex flex-col items-center font-sans relative z-10">
            
            <div className="w-full max-w-4xl p-4 sm:p-8 flex-none space-y-6 sm:space-y-8 relative z-10">

                {/* ── Page Header ─────────────────────────────────────── */}
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-6 sm:mb-8 mt-2">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight text-pro-text mb-1">
                            About QuantSight Cloud
                        </h1>
                        <p className="text-sm text-pro-muted mt-2">
                            Platform overview, capabilities, and legal reference.
                        </p>
                    </div>
                    <div className="self-start px-3 py-1.5 border border-emerald-500/50 rounded-xl bg-emerald-500/5">
                        <span className="text-emerald-500 text-xs font-mono font-medium tracking-wide">
                            Version 4.1.2
                        </span>
                    </div>
                </div>

                {/* ── Section 1: What Is QuantSight Cloud ─────────────── */}
                <section className="p-6 rounded-xl border border-pro-border bg-pro-surface relative shadow-sm" >
                    
                    <h2 className="text-xs tracking-wide text-emerald-500 font-bold uppercase mb-5 relative z-10">
                        What Is QuantSight Cloud
                    </h2>
                    <div className="space-y-4 relative z-10 text-sm text-pro-text leading-relaxed">
                        <p>
                            QuantSight Cloud is a real-time sports analytics platform built for
                            serious analysts who want data-driven insight without the noise.
                            Powered by modern cloud infrastructure and an AI-driven intelligence
                            layer, QuantSight brings together live game data, historical player
                            analysis, matchup modeling, and real-time streaming into a single
                            unified platform.
                        </p>
                        <p>
                            From live game feeds to deep player profiling, QuantSight is designed
                            to give analysts the information architecture they need to think
                            clearly and act decisively.
                        </p>
                    </div>
                </section>

                {/* ── Section 2: Platform Capabilities ────────────────── */}
                <section className="p-6 rounded-xl border border-pro-border bg-pro-surface relative shadow-sm" >
                    
                    <h2 className="text-xs tracking-wide text-blue-500 font-bold uppercase mb-5 relative z-10">
                        Platform Capabilities
                    </h2>
                    <p className="text-sm text-pro-text leading-relaxed mb-5 relative z-10">
                        QuantSight Cloud provides a comprehensive suite of analytical tools
                        built on a distributed, production-grade cloud architecture.
                    </p>

                    <div className="space-y-4 relative z-10">
                        {[
                            {
                                name: 'Live Game Intelligence',
                                color: 'text-emerald-500',
                                border: 'border-l-emerald-500/50',
                                desc: 'Real-time game data, live scoring feeds, and WebSocket-powered updates that keep every view current without manual refreshing.',
                            },
                            {
                                name: 'Player Analysis',
                                color: 'text-blue-500',
                                border: 'border-l-blue-500/50',
                                desc: 'Deep player profiling with historical game logs, head-to-head matchup analysis, usage metrics, and performance projections built on verified statistical frameworks.',
                            },
                            {
                                name: 'Matchup Engine',
                                color: 'text-purple-500',
                                border: 'border-l-purple-500/50',
                                desc: 'Structured matchup analysis across players and teams, with crucible simulation and usage vacuum modeling for advanced scenario analysis.',
                            },
                            {
                                name: 'Vanguard Intelligence',
                                color: 'text-amber-500',
                                border: 'border-l-amber-500/50',
                                desc: 'An AI-powered internal intelligence layer that monitors platform health, triages analytical incidents, and operates in fully sovereign mode for autonomous decision-making.',
                            },
                            {
                                name: 'Pulse',
                                color: 'text-red-500',
                                border: 'border-l-red-500/50',
                                desc: 'A dedicated real-time streaming service delivering live leaders, live game states, and WebSocket broadcast capability to every connected client simultaneously.',
                            },
                        ].map((cap) => (
                            <div
                                key={cap.name}
                                className={`pl-4 border-l-2 ${cap.border} bg-white/[0.02] rounded-xl p-4`}
                            >
                                <div className={`text-sm font-semibold tracking-tight ${cap.color} mb-1`}>
                                    {cap.name}
                                </div>
                                <p className="text-sm text-pro-muted leading-relaxed">
                                    {cap.desc}
                                </p>
                            </div>
                        ))}
                    </div>
                </section>

                {/* ── Section 3: Who This Platform Is For ──────────────── */}
                <section className="p-6 rounded-xl border border-pro-border bg-pro-surface relative shadow-sm" >
                    
                    <h2 className="text-xs tracking-wide text-emerald-500 font-bold uppercase mb-5 relative z-10">
                        Who This Platform Is For
                    </h2>
                    <div className="space-y-4 relative z-10 text-sm text-pro-text leading-relaxed">
                        <p>
                            QuantSight Cloud is built for analysts, researchers, and sports
                            data professionals who demand precision, reliability, and depth.
                            This is not a casual stats browser. It is a platform built with
                            production-grade infrastructure, enterprise-level observability,
                            and an analytical framework developed through rigorous real-world
                            testing.
                        </p>
                        <p>
                            Whether you are analyzing a single player's trajectory or running
                            multi-game simultaneous analysis, QuantSight provides the data
                            architecture to support serious work.
                        </p>
                    </div>
                </section>

                {/* ── Section 4: Disclaimer (Static Reference) ─────────── */}
                <section className="p-6 rounded-xl border border-amber-500/30 bg-amber-500/5 relative shadow-sm" >
                    
                    <div className="flex items-center gap-2 mb-5 relative z-10">
                        <span className="text-amber-500 text-base font-bold animate-pulse">[!]</span>
                        <h2 className="text-xs tracking-wide text-amber-500 font-bold uppercase">
                            Disclaimer
                        </h2>
                    </div>
                    <div className="space-y-4 relative z-10 text-sm text-pro-text leading-relaxed">
                        <p>
                            QuantSight Cloud is provided for informational and research purposes
                            only. Nothing on this platform constitutes financial advice, betting
                            advice, gambling recommendations, or any form of investment guidance.
                        </p>
                        <p>
                            All data, analysis, projections, and content are provided solely for
                            informational purposes and do not represent a guarantee of any
                            outcome. Sports analytics involve inherent uncertainty. Past
                            performance of any model or framework does not guarantee future
                            results.
                        </p>
                        <p>
                            By using this platform, you acknowledge that you do so entirely at
                            your own risk, that QuantSight Cloud bears no responsibility for any
                            decisions made based on information presented here, and that you are
                            solely responsible for compliance with all applicable laws and
                            regulations in your jurisdiction.
                        </p>
                        <p className="border border-pro-border/50 bg-white/[0.02] p-3 text-center text-amber-500/80 italic mt-6">
                            For questions or concerns regarding this platform, contact the
                            platform administrator directly.
                        </p>
                    </div>
                </section>

                {/* Bottom spacer */}
                <div className="pb-4" />

            </div>
        </div>
    );
}
