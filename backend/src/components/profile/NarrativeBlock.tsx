import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

interface NarrativeBlockProps {
    text: string;
}

export default function NarrativeBlock({ text }: NarrativeBlockProps) {
    const [displayedText, setDisplayedText] = useState('');

    // Typewriter Logic
    useEffect(() => {
        let i = 0;
        setDisplayedText('');
        const speed = 20; // ms per char

        const interval = setInterval(() => {
            if (i < text.length) {
                setDisplayedText((prev) => prev + text.charAt(i));
                i++;
            } else {
                clearInterval(interval);
            }
        }, speed);

        return () => clearInterval(interval);
    }, [text]);

    return (
        <div className="relative p-6 rounded-xl border border-financial-accent/20 bg-gradient-to-b from-financial-accent/5 to-transparent backdrop-blur-sm">
            <div className="flex items-center gap-2 mb-4">
                <div className="w-2 h-2 bg-financial-accent rounded-full animate-pulse" />
                <h3 className="text-xs font-bold text-financial-accent uppercase tracking-widest">Stratos Narrative Relay</h3>
            </div>

            <p className="font-mono text-sm leading-relaxed text-slate-300 min-h-[100px] whitespace-pre-wrap">
                {displayedText}
                <motion.span
                    animate={{ opacity: [0, 1, 0] }}
                    transition={{ repeat: Infinity, duration: 0.8 }}
                    className="inline-block w-2 l-4 bg-financial-accent ml-1 align-middle h-4"
                />
            </p>
        </div>
    );
}
