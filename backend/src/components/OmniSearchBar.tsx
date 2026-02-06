import { useState, useMemo, useEffect, useRef } from 'react'
import Fuse, { FuseResult } from 'fuse.js'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'

// Player search will be populated from backend API
interface Player {
    id: string
    name: string
    team: string
    position: string
    avatar?: string
}


import { useNavigate } from 'react-router-dom';

export default function OmniSearchBar() {
    const [query, setQuery] = useState('')
    const [isOpen, setIsOpen] = useState(false)
    const [selectedIndex, setSelectedIndex] = useState(0)
    const [allPlayers, setAllPlayers] = useState<Player[]>([])
    const inputRef = useRef<HTMLInputElement>(null)
    const navigate = useNavigate();

    // Load all players from backend on mount
    useEffect(() => {
        const loadPlayers = async () => {
            try {
                let response;

                // Always use direct HTTP in dev mode for reliability
                const isDev = window.location.hostname === 'localhost' && window.location.port === '5173';

                if (!isDev && window.electronAPI) {
                    // Electron mode (production)
                    console.log('[OmniSearch] Loading players via Electron IPC');
                    response = await window.electronAPI.searchPlayers('');

                    // Fallback to HTTP if IPC returns nothing
                    if (!response || (Array.isArray(response) && response.length === 0)) {
                        console.warn('[OmniSearch] IPC returned no data, falling back to direct HTTP');
                        const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/players/search?q=');
                        if (res.ok) {
                            response = await res.json();
                        }
                    }
                } else {
                    // Browser/Dev mode - direct API call
                    console.log('[OmniSearch] Loading players via direct HTTP');
                    const res = await fetch('https://quantsight-cloud-458498663186.us-central1.run.app/players/search?q=');
                    if (!res.ok) {
                        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
                    }
                    response = await res.json();
                }

                if (response && Array.isArray(response)) {
                    console.log(`[OmniSearch] Successfully loaded ${response.length} players`);
                    setAllPlayers(response);
                } else {
                    console.warn('[OmniSearch] Invalid response format:', response);
                    setAllPlayers([]);
                }
            } catch (error) {
                console.error('[OmniSearch] Failed to load players:', error);

                // Retry after 2 seconds
                setTimeout(() => {
                    console.log('[OmniSearch] Retrying player load...');
                    loadPlayers();
                }, 2000);
            }
        };
        loadPlayers();
    }, []);

    // Initialize Fuse
    const fuse = useMemo(() => {
        console.log(`Initializing Fuse with ${allPlayers.length} players`);
        return new Fuse(allPlayers, {
            keys: ['name', 'team', 'position'],
            threshold: 0.4, // Relaxed from 0.3 for better typo tolerance
        })
    }, [allPlayers])


    const results: FuseResult<Player>[] = useMemo(() => {
        if (!query) return []
        return fuse.search(query).slice(0, 5) // Limit to top 5
    }, [query, fuse])

    // Reset selection when results change
    useEffect(() => {
        setSelectedIndex(0)
    }, [results])

    const handleSelect = (item: Player) => {
        console.log("Selected Player:", item.name)
        navigate(`/player/${item.id}`)
        setIsOpen(false)
        setQuery('')
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault()
            setSelectedIndex(prev => Math.min(prev + 1, results.length - 1))
        } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setSelectedIndex(prev => Math.max(prev - 1, 0))
        } else if (e.key === 'Enter') {
            e.preventDefault()
            const selected = results[selectedIndex]?.item
            if (selected) {
                handleSelect(selected);
            }
        } else if (e.key === 'Escape') {
            setIsOpen(false)
        }
    }

    return (
        <div className="relative w-full max-w-lg mx-auto">
            {/* Search Input */}
            <div className={`
        relative flex items-center bg-slate-800/50 rounded-lg border border-slate-600 
        focus-within:border-financial-accent focus-within:shadow-[0_0_15px_rgba(100,255,218,0.1)]
        transition-all duration-300 backdrop-blur-sm
      `}>
                <div className="pl-4 text-slate-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <input
                    ref={inputRef}
                    type="text"
                    className="w-full bg-transparent border-none focus:ring-0 text-white placeholder-slate-500 py-2 px-3 text-sm"
                    placeholder="Search players, teams, or metrics..."
                    value={query}
                    onChange={(e) => {
                        setQuery(e.target.value)
                        setIsOpen(true)
                    }}
                    onKeyDown={handleKeyDown}
                    onFocus={() => { if (query) setIsOpen(true) }}
                    onBlur={() => setTimeout(() => setIsOpen(false), 200)}
                />
                {/* CMD+K shortcut hint removed */}
            </div>

            {/* Results Dropdown */}
            {isOpen && results.length > 0 && (
                <div className="absolute top-full mt-2 w-full bg-slate-800/90 border border-slate-700 rounded-lg shadow-2xl backdrop-blur-xl overflow-hidden z-50">
                    <div className="text-[10px] uppercase text-slate-500 px-3 py-2 font-bold tracking-wider bg-black/20">
                        Players
                    </div>
                    <ul>
                        {results.map(({ item }, index) => (
                            <li
                                key={item.id}
                                className={`
                  flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors
                  ${index === selectedIndex ? 'bg-financial-accent/10 border-l-2 border-financial-accent' : 'hover:bg-slate-700/50 border-l-2 border-transparent'}
                `}
                                onMouseEnter={() => setSelectedIndex(index)}
                                onClick={() => {
                                    handleSelect(item);
                                }}
                            >
                                <img src={getPlayerAvatarUrl(item.id)} alt={item.name} className="w-8 h-8 rounded-full border border-slate-600 bg-slate-900 object-cover" />
                                <div className="flex-1">
                                    <div className="text-sm font-medium text-slate-200">{item.name}</div>
                                    <div className="text-xs text-slate-400">{item.team} • {item.position}</div>
                                </div>
                                {index === selectedIndex && (
                                    <div className="text-xs text-financial-accent opacity-50">↩</div>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}
