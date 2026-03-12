import { useState, useMemo, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom';
import Fuse, { FuseResult } from 'fuse.js'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { PlayerApi } from '../services/playerApi'
import CornerBrackets from './common/CornerBrackets';

// Player search will be populated from backend API
interface Player {
    id: string
    name: string
    team: string
    position: string
    avatar?: string
}

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
                const response = await PlayerApi.search('');

                if (response && Array.isArray(response)) {
                    setAllPlayers(response);
                } else {
                    console.warn('[OmniSearch] Invalid response format:', response);
                    setAllPlayers([]);
                }
            } catch (error) {
                console.error('[OmniSearch] Failed to load players:', error);

                // Retry after 2 seconds
                setTimeout(() => {
                    loadPlayers();
                }, 2000);
            }
        };
        loadPlayers();
    }, []);

    // Initialize Fuse
    const fuse = useMemo(() => {
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
        relative flex items-center bg-cyber-surface rounded-sm border border-cyber-border 
        focus-within:border-cyber-blue 
        transition-all duration-100
      `}>
                <div className="pl-4 text-cyber-muted">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <input
                    ref={inputRef}
                    type="text"
                    className="w-full bg-transparent border-none focus:ring-0 text-cyber-text placeholder-cyber-muted font-mono py-2 px-3 text-xs"
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
                <div className="absolute top-full mt-2 w-full bg-cyber-bg border border-cyber-border shadow-2xl z-50 rounded-sm relative" style={{ border: '1px solid #1a2332' }}>
                    <CornerBrackets />
                    <div className="text-[10px] uppercase text-cyber-muted px-3 py-2 font-display font-600 tracking-[0.12em] bg-white/[0.02]">
                        Players
                    </div>
                    <ul>
                        {results.map(({ item }, index) => (
                            <li
                                key={item.id}
                                className={`
                  flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors duration-100
                  ${index === selectedIndex ? 'bg-cyber-blue/10 border-l-2 border-cyber-blue' : 'hover:bg-white/[0.05] border-l-2 border-transparent'}
                `}
                                onMouseEnter={() => setSelectedIndex(index)}
                                onClick={() => {
                                    handleSelect(item);
                                }}
                            >
                                <img src={getPlayerAvatarUrl(item.id)} alt={item.name} className="w-8 h-8 rounded-sm border border-cyber-border bg-cyber-surface object-cover" />
                                <div className="flex-1">
                                    <div className="text-sm font-display font-600 tracking-[0.08em] uppercase text-cyber-text">{item.name}</div>
                                    <div className="text-[10px] uppercase text-cyber-muted tracking-widest">{item.team} • {item.position}</div>
                                </div>
                                {index === selectedIndex && (
                                    <div className="text-xs text-cyber-blue opacity-50">↩</div>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}
