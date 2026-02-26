/**
 * useAnnotations — Phase 8 Step 8.6.2
 * ======================================
 * React hook for collaborative annotations with real-time updates.
 *
 * - Loads initial annotations via HTTP on mount
 * - Listens for real-time additions via WebSocket
 * - Provides addAnnotation() for creating new notes
 *
 * Usage:
 *   const { annotations, addAnnotation } = useAnnotations('player', '2544');
 *   addAnnotation('Great performance tonight!');
 */

import { useState, useEffect, useCallback } from 'react';
import { wsClient } from '../services/wsClient';

export interface Annotation {
    note_id: string;
    author_token: string;
    content: string;
    created_at: string;
    edited_at: string | null;
    pinned: boolean;
    reactions: {
        '👍': number;
        '🔥': number;
        '⚠️': number;
    };
}

interface AnnotationEvent {
    note: Annotation;
    context_type: string;
    context_id: string;
}

interface ReactionEvent {
    context_type: string;
    context_id: string;
    note_id: string;
    reaction: string;
}

const API_BASE = 'https://quantsight-cloud-458498663186.us-central1.run.app';

export function useAnnotations(contextType: string, contextId: string) {
    const [annotations, setAnnotations] = useState<Annotation[]>([]);
    const [loading, setLoading] = useState(true);

    // Load initial annotations via HTTP
    useEffect(() => {
        if (!contextType || !contextId) return;

        setLoading(true);
        fetch(`${API_BASE}/annotations/${contextType}/${contextId}`)
            .then(r => r.json())
            .then(data => {
                setAnnotations(data.notes ?? []);
                setLoading(false);
            })
            .catch(() => {
                setLoading(false);
            });
    }, [contextType, contextId]);

    // Listen for real-time annotation additions
    useEffect(() => {
        const unsubAnnotation = wsClient.on('annotation_added', (data: unknown) => {
            const d = data as AnnotationEvent;
            if (d.context_type === contextType && d.context_id === contextId) {
                setAnnotations(prev => [d.note, ...prev].slice(0, 50));
            }
        });

        // Listen for reaction updates
        const unsubReaction = wsClient.on('reaction_added', (data: unknown) => {
            const d = data as ReactionEvent;
            if (d.context_type === contextType && d.context_id === contextId) {
                setAnnotations(prev =>
                    prev.map(note => {
                        if (note.note_id === d.note_id) {
                            const key = d.reaction as keyof Annotation['reactions'];
                            return {
                                ...note,
                                reactions: {
                                    ...note.reactions,
                                    [key]: (note.reactions[key] ?? 0) + 1,
                                },
                            };
                        }
                        return note;
                    }),
                );
            }
        });

        return () => {
            unsubAnnotation();
            unsubReaction();
        };
    }, [contextType, contextId]);

    // Create a new annotation
    const addAnnotation = useCallback(
        (content: string) => {
            wsClient.annotate(contextType, contextId, content);
        },
        [contextType, contextId],
    );

    // Add a reaction to a note
    const addReaction = useCallback(
        (noteId: string, reaction: string) => {
            wsClient.react(contextType, contextId, noteId, reaction);
        },
        [contextType, contextId],
    );

    return { annotations, addAnnotation, addReaction, loading };
}

export default useAnnotations;
