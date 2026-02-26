import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Trash2, RefreshCw, Plus, User } from 'lucide-react';
import { useOrbital } from '@/context/OrbitalContext';
import { PlayerApi, PlayerProfile } from '@/services/playerApi';
import { ApiContract } from '@/api/client';

const NBA_TEAMS = [
    'ATL', 'BOS', 'BKN', 'CHA', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW',
    'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA', 'MIL', 'MIN', 'NOP', 'NYK',
    'OKC', 'ORL', 'PHI', 'PHX', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS'
];

interface Injury {
    player_id: string;
    player_name: string;
    team_abbr: string;
    status: string;
    injury_desc: string;
}

interface FormData {
    player_id: string;
    player_name: string;
    team: string;
    status: string;
    injury_desc: string;
}

interface Message {
    type: 'success' | 'error' | '';
    text: string;
}

export default function InjuryAdmin() {
    const { selectedPlayer } = useOrbital();
    const [injuries, setInjuries] = useState<Injury[]>([]);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState<Message>({ type: '', text: '' });
    const [playerSearch, setPlayerSearch] = useState('');
    const [searchResults, setSearchResults] = useState<PlayerProfile[]>([]);
    const [showSearchResults, setShowSearchResults] = useState(false);

    const [formData, setFormData] = useState<FormData>({
        player_id: '',
        player_name: '',
        team: '',
        status: 'OUT',
        injury_desc: ''
    });

    useEffect(() => {
        loadInjuries();
    }, []);

    // Auto-fill from selected player in context
    useEffect(() => {
        if (selectedPlayer) {
            setFormData(prev => ({
                ...prev,
                player_id: selectedPlayer.id,
                player_name: selectedPlayer.name,
                team: selectedPlayer.team?.toUpperCase() || ''
            }));
            setPlayerSearch(selectedPlayer.name);
        }
    }, [selectedPlayer]);

    // Player search with debounce
    useEffect(() => {
        if (playerSearch.length < 2) {
            setSearchResults([]);
            return;
        }

        const timer = setTimeout(async () => {
            try {
                const results = await PlayerApi.search(playerSearch);
                setSearchResults(results.slice(0, 8));
            } catch (err) {
                console.error('Player search failed:', err);
            }
        }, 300);

        return () => clearTimeout(timer);
    }, [playerSearch]);

    const loadInjuries = async () => {
        setLoading(true);
        try {
            const res = await ApiContract.execute<any>('getInjuries', { path: 'injuries' });
            const data = res.data;
            setInjuries(data.injuries || []);
        } catch (err) {
            showMessage('error', 'Failed to load injuries');
        } finally {
            setLoading(false);
        }
    };

    const handleSelectPlayer = (player: PlayerProfile) => {
        setFormData(prev => ({
            ...prev,
            player_id: player.id,
            player_name: player.name,
            team: player.team?.toUpperCase() || ''
        }));
        setPlayerSearch(player.name);
        setShowSearchResults(false);
    };

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();

        try {
            const res = await ApiContract.execute<any>('addInjury', {
                path: 'admin/injuries/add',
                options: {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                }
            });

            if (res.data) {
                showMessage('success', 'Injury added successfully!');
                setFormData({
                    player_id: '',
                    player_name: '',
                    team: '',
                    status: 'OUT',
                    injury_desc: ''
                });
                setPlayerSearch('');
                loadInjuries();
            } else {
                showMessage('error', 'Failed to add injury');
            }
        } catch (err) {
            showMessage('error', 'Error: ' + (err instanceof Error ? err.message : 'Unknown error'));
        }
    };

    const removeInjury = async (playerId: string) => {
        if (!confirm('Remove this injury?')) return;

        try {
            const res = await ApiContract.execute<any>('removeInjury', {
                path: `admin/injuries/remove/${playerId}`,
                options: {
                    method: 'DELETE'
                }
            });

            if (res.data) {
                showMessage('success', 'Injury removed!');
                loadInjuries();
            } else {
                showMessage('error', 'Failed to remove injury');
            }
        } catch (err) {
            showMessage('error', 'Error: ' + (err instanceof Error ? err.message : 'Unknown error'));
        }
    };

    const showMessage = (type: 'success' | 'error', text: string) => {
        setMessage({ type, text });
        setTimeout(() => setMessage({ type: '', text: '' }), 3000);
    };

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <div className="p-6 pb-4">
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-blue-600 bg-clip-text text-transparent">
                    ⚕️ Injury Management
                </h1>
                <p className="text-slate-400 mt-2">Manage player injuries and status updates</p>
            </div>

            <div className="flex-1 overflow-y-auto px-6 space-y-6">
                {message.text && (
                    <Alert className={message.type === 'success' ? 'border-green-500 bg-green-500/10' : 'border-red-500 bg-red-500/10'}>
                        <AlertDescription>{message.text}</AlertDescription>
                    </Alert>
                )}

                {/* Add Injury Form */}
                <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader>
                        <CardTitle className="text-blue-400">Add/Update Injury</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* Player Search with Dropdown */}
                            <div>
                                <Label htmlFor="playerSearch">Search Player</Label>
                                <div className="relative">
                                    <Input
                                        id="playerSearch"
                                        value={playerSearch}
                                        onChange={(e) => {
                                            setPlayerSearch(e.target.value);
                                            setShowSearchResults(true);
                                        }}
                                        onFocus={() => setShowSearchResults(true)}
                                        placeholder="Start typing player name..."
                                        className="bg-slate-900 border-slate-600"
                                    />
                                    {showSearchResults && searchResults.length > 0 && (
                                        <div className="absolute z-10 w-full mt-1 bg-slate-800 border border-slate-600 rounded-md shadow-lg max-h-48 overflow-y-auto">
                                            {searchResults.map((player) => (
                                                <div
                                                    key={player.id}
                                                    onClick={() => handleSelectPlayer(player)}
                                                    className="px-4 py-2 hover:bg-slate-700 cursor-pointer flex items-center gap-2"
                                                >
                                                    <User className="w-4 h-4 text-blue-400" />
                                                    <span>{player?.name || 'Unknown'}</span>
                                                    <span className="text-xs text-slate-400">({player?.team || 'N/A'})</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <Label htmlFor="playerId">Player ID</Label>
                                    <Input
                                        id="playerId"
                                        value={formData.player_id}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, player_id: e.target.value })}
                                        placeholder="e.g. 1628983"
                                        required
                                        className="bg-slate-900 border-slate-600"
                                        readOnly
                                    />
                                </div>
                                <div>
                                    <Label htmlFor="playerName">Player Name</Label>
                                    <Input
                                        id="playerName"
                                        value={formData.player_name}
                                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, player_name: e.target.value })}
                                        placeholder="e.g. Austin Reaves"
                                        required
                                        className="bg-slate-900 border-slate-600"
                                        readOnly
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <Label htmlFor="team">Team</Label>
                                    <Select
                                        value={formData.team}
                                        onValueChange={(value: string) => setFormData({ ...formData, team: value })}
                                    >
                                        <SelectTrigger className="bg-slate-900 border-slate-600">
                                            <SelectValue placeholder="Select team..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {NBA_TEAMS.map(team => (
                                                <SelectItem key={team} value={team}>{team}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <Label htmlFor="status">Status</Label>
                                    <Select
                                        value={formData.status}
                                        onValueChange={(value: string) => setFormData({ ...formData, status: value })}
                                    >
                                        <SelectTrigger className="bg-slate-900 border-slate-600">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="OUT">OUT</SelectItem>
                                            <SelectItem value="QUESTIONABLE">QUESTIONABLE</SelectItem>
                                            <SelectItem value="PROBABLE">PROBABLE</SelectItem>
                                            <SelectItem value="DOUBTFUL">DOUBTFUL</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div>
                                <Label htmlFor="injuryDesc">Injury Description</Label>
                                <Input
                                    id="injuryDesc"
                                    value={formData.injury_desc}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setFormData({ ...formData, injury_desc: e.target.value })}
                                    placeholder="e.g. Left calf strain"
                                    required
                                    className="bg-slate-900 border-slate-600"
                                />
                            </div>

                            <Button type="submit" className="bg-blue-600 hover:bg-blue-700">
                                <Plus className="w-4 h-4 mr-2" />
                                Add Injury
                            </Button>
                        </form>
                    </CardContent>
                </Card>

                {/* Current Injuries - Scrollable */}
                <Card className="bg-slate-800/50 border-slate-700">
                    <CardHeader className="flex flex-row items-center justify-between">
                        <CardTitle className="text-blue-400">Current Injuries</CardTitle>
                        <Button
                            onClick={loadInjuries}
                            disabled={loading}
                            variant="outline"
                            size="sm"
                            className="border-slate-600"
                        >
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </CardHeader>
                    <CardContent>
                        <div className="max-h-96 overflow-y-auto space-y-2 pr-2">
                            {injuries.length === 0 ? (
                                <p className="text-slate-400 text-center py-8">No injuries to display</p>
                            ) : (
                                injuries.map((inj) => (
                                    <div
                                        key={inj.player_id}
                                        className="flex items-center justify-between p-4 bg-slate-900/50 border-l-4 border-red-500 rounded-r"
                                    >
                                        <div className="flex-1">
                                            <div className="font-semibold text-lg">
                                                {inj.player_name} ({inj.team_abbr})
                                            </div>
                                            <div className="flex items-center gap-2 mt-1">
                                                <span className={`px-3 py-1 rounded text-xs font-semibold ${inj.status === 'OUT' ? 'bg-red-500' :
                                                    inj.status === 'QUESTIONABLE' ? 'bg-yellow-500' :
                                                        'bg-green-500'
                                                    }`}>
                                                    {inj.status}
                                                </span>
                                                <span className="text-slate-400">{inj.injury_desc}</span>
                                            </div>
                                        </div>
                                        <Button
                                            onClick={() => removeInjury(inj.player_id)}
                                            variant="destructive"
                                            size="sm"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                ))
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
