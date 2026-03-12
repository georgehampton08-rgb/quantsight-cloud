import { useState, useMemo, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom';
import Fuse, { FuseResult } from 'fuse.js'
import { getPlayerAvatarUrl } from '../utils/avatarUtils'
import { PlayerApi } from '../services/playerApi'

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
        relative flex items-center bg-pro-surface rounded-xl border border-pro-border 
        focus-within:border-blue-500 
        transition-all duration-100 shadow-sm
      `}>
                <div className="pl-4 text-pro-muted">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <input
                    ref={inputRef}
                    type="text"
                    className="w-full bg-transparent border-none focus:ring-0 text-pro-text placeholder-pro-muted font-sans py-2 px-3 text-sm"
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
            </div>

            {/* Results Dropdown */}
            {isOpen && results.length > 0 && (
                <div className="absolute top-full mt-2 w-full bg-pro-bg border border-pro-border shadow-sm z-50 rounded-xl relative" >
                    
                    <div className="text-xs uppercase text-pro-muted px-3 py-2 font-semibold tracking-normal bg-white/[0.02]">
                        Players
                    </div>
                    <ul>
                        {results.map(({ item }, index) => (
                            <li
                                key={item.id}
                                className={`
                  flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors duration-100
                  ${index === selectedIndex ? 'bg-blue-500/10 border-l-2 border-blue-500' : 'hover:bg-white/[0.05] border-l-2 border-transparent'}
                `}
                                onMouseEnter={() => setSelectedIndex(index)}
                                onClick={() => {
                                    handleSelect(item);
                                }}
                            >
                                <img src={getPlayerAvatarUrl(item.id)} alt={item.name} className="w-8 h-8 rounded-xl border border-pro-border bg-pro-surface object-cover" />
                                <div className="flex-1">
                                    <div className="text-sm font-semibold tracking-normal uppercase text-pro-text">{item.name}</div>
                                    <div className="text-xs uppercase text-pro-muted tracking-wide">{item.team} • {item.position}</div>
                                </div>
                                {index === selectedIndex && (
                                    <div className="text-xs text-blue-500 opacity-50 font-mono tracking-wide">{'>'}</div>
                                )}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    )
}
