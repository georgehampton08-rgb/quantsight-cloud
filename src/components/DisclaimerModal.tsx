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
            className="qs-disclaimer-overlay"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="disclaimer-title"
        >
            <div className="qs-disclaimer-card">
                {/* Top accent bar */}
                <div className="qs-disclaimer-accent-bar" />

                {/* Header */}
                <div className="qs-disclaimer-header">
                    <div className="qs-disclaimer-icon">⚠️</div>
                    <h2 id="disclaimer-title" className="qs-disclaimer-title">
                        Important Disclaimer
                    </h2>
                </div>

                {/* Scrollable body */}
                <div className="qs-disclaimer-body">
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

                    <p>By using this platform, you acknowledge and agree that:</p>

                    <ul className="qs-disclaimer-list">
                        <li>You are using this platform entirely at your own risk</li>
                        <li>
                            QuantSight Cloud is not responsible for any decisions made
                            based on information presented here
                        </li>
                        <li>
                            No content on this platform should be interpreted as a
                            recommendation to place any wager, bet, or financial transaction
                        </li>
                        <li>
                            You are solely responsible for complying with all applicable
                            laws and regulations in your jurisdiction
                        </li>
                    </ul>

                    <p className="qs-disclaimer-footer-note">
                        If you do not agree to these terms, please do not use this platform.
                    </p>
                </div>

                {/* Acknowledgment button */}
                <div className="qs-disclaimer-actions">
                    <button
                        id="disclaimer-acknowledge-btn"
                        className="qs-disclaimer-btn"
                        onClick={handleAcknowledge}
                    >
                        I Understand and Agree
                    </button>
                </div>
            </div>
        </div>
    );
}
