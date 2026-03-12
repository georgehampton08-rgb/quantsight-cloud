/**
 * DisclaimerModal
 * ================
 * Appears once per browser session. Uses sessionStorage key
 * `qs_disclaimer_acknowledged` to suppress on page refresh but
 * re-show on every new browser session (sessionStorage clears on
 * browser close).
 *
 * The modal is blocking — no outside-click or Escape dismissal.
 * The only exit is clicking "I Understand and Agree".
 */

import { useState, useEffect, useCallback } from 'react';
import CornerBrackets from './common/CornerBrackets';

const SESSION_KEY = 'qs_disclaimer_acknowledged';

export default function DisclaimerModal() {
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        // Only show if this session has not yet acknowledged
        const acknowledged = sessionStorage.getItem(SESSION_KEY);
        if (!acknowledged) {
            setVisible(true);
        }
    }, []);

    const handleAcknowledge = useCallback(() => {
        sessionStorage.setItem(SESSION_KEY, 'true');
        setVisible(false);
    }, []);

    // Block Escape key while modal is open
    useEffect(() => {
        if (!visible) return;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.preventDefault();
                e.stopPropagation();
            }
        };
        window.addEventListener('keydown', handleKeyDown, true);
        return () => window.removeEventListener('keydown', handleKeyDown, true);
    }, [visible]);

    if (!visible) return null;

    return (
        /*
         * Overlay: full-screen, dark, pointer-events-all so clicks on the
         * backdrop are captured and swallowed (no dismiss on outside click).
         */
        <div
            className="fixed inset-0 z-[9999] bg-black/90 flex items-center justify-center p-4 font-sans"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="disclaimer-title"
        >
            <div className="absolute inset-0 pointer-events-none opacity-[0.03] z-0"
                 style={{
                   backgroundImage: 'linear-gradient(#00ff88 1px, transparent 1px), linear-gradient(90deg, #00ff88 1px, transparent 1px)',
                   backgroundSize: '32px 32px',
                 }} />
            <div className="bg-cyber-surface border border-cyber-border rounded-none p-6 sm:p-8 max-w-2xl w-full relative z-10 animate-in fade-in zoom-in-95 duration-200" style={{ border: '1px solid #1a2332' }}>
                <CornerBrackets />

                {/* Top accent bar */}
                <div className="absolute top-0 left-0 w-full h-1 bg-cyber-gold opacity-50" />

                {/* Header */}
                <div className="flex items-center gap-3 border-b border-cyber-border/50 pb-4 mb-6 relative z-10">
                    <div className="text-cyber-gold font-mono font-bold animate-pulse">
                        [!]
                    </div>
                    <h2 id="disclaimer-title" className="text-xl sm:text-2xl font-display font-700 tracking-[0.08em] uppercase text-cyber-text">
                        Important Disclaimer
                    </h2>
                </div>

                {/* Scrollable body */}
                <div className="text-cyber-muted font-mono text-xs sm:text-sm leading-relaxed space-y-4 max-h-[60vh] overflow-y-auto scrollbar-premium pr-2 relative z-10">
                    <p>
                        QuantSight Cloud is an independent sports analytics platform provided
                        for informational and research purposes only.
                    </p>

                    <p>
                        Nothing on this platform constitutes financial advice, betting advice,
                        gambling recommendations, or any form of investment guidance. All
                        data, analysis, projections, statistics, and content displayed on
                        this platform are provided solely for informational purposes and do
                        not represent a guarantee of any outcome.
                    </p>

                    <p>
                        Sports analytics involve inherent uncertainty. Past performance of
                        any analytical model, framework, or data point does not guarantee
                        future results. QuantSight Cloud makes no representations or
                        warranties regarding the accuracy, completeness, or timeliness of
                        any information presented.
                    </p>

                    <p className="text-cyber-text font-bold">By using this platform, you acknowledge and agree that:</p>

                    <ul className="list-none space-y-2">
                        <li className="flex items-start gap-2">
                            <span className="text-cyber-gold mt-0.5">{'>'}</span>
                            You are using this platform entirely at your own risk
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-cyber-gold mt-0.5">{'>'}</span>
                            QuantSight Cloud is not responsible for any decisions made based on information presented here
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-cyber-gold mt-0.5">{'>'}</span>
                            No content on this platform should be interpreted as a recommendation to place any wager, bet, or financial transaction
                        </li>
                        <li className="flex items-start gap-2">
                            <span className="text-cyber-gold mt-0.5">{'>'}</span>
                            You are solely responsible for complying with all applicable laws and regulations in your jurisdiction
                        </li>
                    </ul>

                    <p className="border border-cyber-border/50 bg-white/[0.02] p-3 mt-6 text-center text-cyber-gold/80 italic">
                        If you do not agree to these terms, please do not use this platform.
                    </p>
                </div>

                {/* Acknowledgment button */}
                <div className="mt-8 flex justify-end relative z-10">
                    <button
                        id="disclaimer-acknowledge-btn"
                        className="bg-cyber-gold/10 hover:bg-cyber-gold/20 border border-cyber-gold text-cyber-gold font-display font-600 tracking-[0.1em] uppercase px-6 py-3 rounded-none transition-all duration-100 w-full sm:w-auto text-xs"
                        onClick={handleAcknowledge}
                    >
                        I Understand and Agree
                    </button>
                </div>
            </div>
        </div>
    );
}
