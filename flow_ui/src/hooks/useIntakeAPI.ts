import { useState, useEffect, useCallback } from 'react';
import { IntakeStep, SessionInfo } from '../types/IntakeTypes';

// Configuration for your Python backend
const API_BASE_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000/ws';

interface UseIntakeAPIReturn {
  sessionInfo: SessionInfo | null;
  steps: IntakeStep[];
  loading: boolean;
  error: string | null;
  startSession: (launchVoice?: boolean) => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  insertStepAfter: (params: { insert_after: string; ask_prompt: string; name?: string; input_key?: string; validate_regex?: string | null; system_prompt?: string | null; flow_name?: string; }) => Promise<boolean>;
  updateStep: (params: { name: string; ask_prompt?: string; input_key?: string; validate_regex?: string | null; system_prompt?: string | null; next_name?: string | null; flow_name?: string; }) => Promise<boolean>;
  deleteStep: (params: { name: string; flow_name?: string; }) => Promise<boolean>;
}

export const useIntakeAPI = (): UseIntakeAPIReturn => {
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [steps, setSteps] = useState<IntakeStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Load flow steps from your backend
  const loadSteps = useCallback(async () => {
    console.log('DEBUG Loading steps from API...');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/flows/injury_intake_strict/steps`);
      const stepsData = await res.json();
      console.log('DEBUG Steps loaded:', stepsData);
      setSteps(stepsData);
    } catch (e: any) {
      console.error('ERROR Failed to load steps:', e);
      setError(e.message || 'Failed to load steps');
    } finally { 
      setLoading(false); 
    }
  }, []);

  // Start a new intake session
  const startSession = useCallback(async (launchVoice: boolean = false) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/intake/start`, {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ 
          flow_name: 'injury_intake_strict',
          launch_voice: launchVoice
        })
      });
      const data = await res.json();
      setSessionInfo({
        session_id: data.session_id,
        flow_name: 'injury_intake_strict',
        state: data.state,
        connected: true
      });

    } catch (e: any) {
      setError(e.message || 'Failed to start session');
    } finally { 
      setLoading(false); 
    }
  }, []);

  // Send a message to the intake system
  const sendMessage = useCallback(async (message: string) => {
    if (!sessionInfo) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/intake/message`, {
        method: 'POST', 
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ session_id: sessionInfo.session_id, message })
      });
      const data = await res.json();
      setSessionInfo(prev => prev ? ({ ...prev, state: data.state }) : prev);
    } catch (e: any) {
      setError(e.message || 'Failed to send message');
    } finally { 
      setLoading(false); 
    }
  }, [sessionInfo]);

  // Insert a new step after an existing one (pre-session compose)
  const insertStepAfter = useCallback(async (params: { insert_after: string; ask_prompt: string; name?: string; input_key?: string; validate_regex?: string | null; system_prompt?: string | null; flow_name?: string; }): Promise<boolean> => {
    const flowName = params.flow_name || 'injury_intake_strict';
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/flows/${encodeURIComponent(flowName)}/steps/insert_after`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          insert_after: params.insert_after,
          ask_prompt: params.ask_prompt,
          name: params.name,
          input_key: params.input_key,
          validate_regex: params.validate_regex,
          system_prompt: params.system_prompt,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || 'Failed to insert step');
        return false;
      }
      // Refresh steps from server to reflect DB order
      await loadSteps();
      return true;
    } catch (e: any) {
      setError(e.message || 'Failed to insert step');
      return false;
    } finally {
      setLoading(false);
    }
  }, [loadSteps]);

  // Update an existing step (pre-session)
  const updateStep = useCallback(async (params: { name: string; ask_prompt?: string; input_key?: string; validate_regex?: string | null; system_prompt?: string | null; next_name?: string | null; flow_name?: string; }): Promise<boolean> => {
    const flowName = params.flow_name || 'injury_intake_strict';
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/flows/${encodeURIComponent(flowName)}/steps/${encodeURIComponent(params.name)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ask_prompt: params.ask_prompt,
          input_key: params.input_key,
          validate_regex: params.validate_regex,
          system_prompt: params.system_prompt,
          next_name: params.next_name,
        }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || 'Failed to update step');
        return false;
      }
      await loadSteps();
      return true;
    } catch (e: any) {
      setError(e.message || 'Failed to update step');
      return false;
    } finally {
      setLoading(false);
    }
  }, [loadSteps]);

  // Delete a step (pre-session)
  const deleteStep = useCallback(async (params: { name: string; flow_name?: string; }): Promise<boolean> => {
    const flowName = params.flow_name || 'injury_intake_strict';
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/flows/${encodeURIComponent(flowName)}/steps/${encodeURIComponent(params.name)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || 'Failed to delete step');
        return false;
      }
      await loadSteps();
      return true;
    } catch (e: any) {
      setError(e.message || 'Failed to delete step');
      return false;
    } finally {
      setLoading(false);
    }
  }, [loadSteps]);

  // WebSocket connection effect
  useEffect(() => {
    if (!sessionInfo) return;

        console.log('DEBUG Setting up WebSocket for session:', sessionInfo.session_id);
        const socket = new WebSocket(WS_URL);

        socket.onopen = () => {
          console.log('DEBUG WebSocket connected, sending session ID');
          socket.send(JSON.stringify({ session_id: sessionInfo.session_id }));
        };

        socket.onmessage = (evt) => {
          const ev = JSON.parse(evt.data);
          console.log('DEBUG WebSocket message received:', ev);

          if (ev.event === 'node_entered') {
            console.log('DEBUG Updating current step to:', ev.node_id);
        setSessionInfo(prev =>
          prev
            ? {
                ...prev,
                state: {
                  ...prev.state,
                  current_step: ev.node_id,
                  collected_data: ev.collected_data || prev.state.collected_data || {},
                  completed_steps: ev.completed_steps || prev.state.completed_steps || [],
                  session_status: ev.node_id === 'completed' ? 'completed' : prev.state.session_status
                }
              }
            : prev
        );
      }
      if (ev.event === 'user_heard') {
        console.log('DEBUG User input heard:', ev.text);
        // Update collected data if provided
        if (ev.collected_data || ev.completed_steps) {
          setSessionInfo(prev => {
            if (!prev) return prev;
            return {
              ...prev,
              state: {
                ...prev.state,
                collected_data: ev.collected_data || prev.state.collected_data || {},
                completed_steps: ev.completed_steps || prev.state.completed_steps || []
              }
            };
          });
        }
      }

      if (ev.event === 'session_ended') {
        console.log('DEBUG Session completed successfully!');
        setSessionInfo(prev => {
          if (!prev) return prev;
          return {
            ...prev,
            state: {
              ...prev.state,
              current_step: 'completed',
              session_status: 'completed'
            }
          };
        });
      }
    };

        socket.onerror = (error) => {
          console.error('ERROR WebSocket error:', error);
        };

        socket.onclose = () => {
          console.log('DEBUG WebSocket closed');
        };

    setWs(socket);
    return () => { 
      console.log('DEBUG Cleaning up WebSocket');
      socket.close(); 
      setWs(null); 
    };
  }, [sessionInfo?.session_id]); // Only depend on session_id

  // Initialize
  useEffect(() => {
    loadSteps();
  }, [loadSteps]);

  return {
    sessionInfo,
    steps,
    loading,
    error,
    startSession,
    sendMessage,
    insertStepAfter,
    updateStep,
    deleteStep,
  };
};