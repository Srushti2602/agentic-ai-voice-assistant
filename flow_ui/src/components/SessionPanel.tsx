import React, { useState } from 'react';
import { SessionInfo, IntakeStep } from '../types/IntakeTypes';

interface SessionPanelProps {
  sessionInfo: SessionInfo | null;
  steps: IntakeStep[];
}

const SessionPanel: React.FC<SessionPanelProps> = ({ sessionInfo, steps }) => {
  const [userInput, setUserInput] = useState('');

  const handleSendMessage = () => {
    if (!userInput.trim()) return;
    
    // TODO: Send message to backend
    console.log('Sending message:', userInput);
    setUserInput('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  if (!sessionInfo) {
    return (
      <div style={{ padding: '20px', textAlign: 'center', color: 'rgba(156, 163, 175, 0.8)' }}>
        <p>Loading session...</p>
      </div>
    );
  }

  const currentStepInfo = steps.find(s => s.name === sessionInfo.state.current_step);
  const progressPercentage = Math.round((sessionInfo.state.completed_steps.length / steps.length) * 100);

  return (
    <div style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column', backgroundColor: 'transparent' }}>
      {/* Session Header */}
      <div style={{ marginBottom: '20px', borderBottom: '1px solid rgba(71, 85, 105, 0.3)', paddingBottom: '15px' }}>
        <h3 style={{ margin: '0 0 10px 0', color: 'rgba(255, 255, 255, 0.9)' }}>Session Info</h3>
        <div style={{ fontSize: '12px', color: 'rgba(156, 163, 175, 0.8)' }}>
          <div><strong>ID:</strong> {sessionInfo.session_id}</div>
          <div><strong>Flow:</strong> {sessionInfo.flow_name}</div>
          <div style={{ display: 'flex', alignItems: 'center', marginTop: '8px' }}>
            <strong>Status:</strong>
            <span style={{
              marginLeft: '8px',
              padding: '2px 8px',
              borderRadius: '12px',
              fontSize: '10px',
              backgroundColor: sessionInfo.connected ? 'rgba(34, 197, 94, 0.8)' : 'rgba(239, 68, 68, 0.8)',
              color: 'white',
              backdropFilter: 'blur(10px)'
            }}>
              {sessionInfo.connected ? 'Connected' : 'Demo Mode'}
            </span>
          </div>
        </div>
      </div>

      {/* Progress */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <h4 style={{ margin: 0, color: 'rgba(255, 255, 255, 0.9)' }}>Progress</h4>
          <span style={{ fontSize: '12px', color: 'rgba(156, 163, 175, 0.8)' }}>{progressPercentage}%</span>
        </div>
        <div style={{
          width: '100%',
          height: '8px',
          backgroundColor: 'rgba(71, 85, 105, 0.4)',
          borderRadius: '4px',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${progressPercentage}%`,
            height: '100%',
            backgroundColor: 'rgba(59, 130, 246, 0.8)',
            transition: 'width 0.3s ease'
          }} />
        </div>
        <div style={{ fontSize: '11px', color: 'rgba(156, 163, 175, 0.8)', marginTop: '4px' }}>
          {sessionInfo.state.completed_steps.length} of {steps.length} steps completed
        </div>
      </div>

      {/* Current Step */}
      <div style={{ marginBottom: '20px' }}>
        <h4 style={{ margin: '0 0 10px 0', color: 'rgba(255, 255, 255, 0.9)' }}>Current Step</h4>
        {currentStepInfo ? (
          <div style={{
            padding: '12px',
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            borderRadius: '8px',
            border: '1px solid rgba(59, 130, 246, 0.4)',
            backdropFilter: 'blur(10px)'
          }}>
            <div style={{ fontWeight: 'bold', color: 'rgba(59, 130, 246, 0.9)', marginBottom: '6px' }}>
              {currentStepInfo.name}
            </div>
            <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.8)', lineHeight: '1.4' }}>
              {currentStepInfo.ask_prompt}
            </div>
          </div>
        ) : (
          <div style={{
            padding: '12px',
            backgroundColor: 'rgba(15, 118, 110, 0.20)',
            borderRadius: '8px',
            border: '1px solid rgba(13, 148, 136, 0.55)',
            color: 'white',
            textAlign: 'center',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 0 0 1px rgba(13,148,136,0.35), 0 0 12px rgba(13,148,136,0.35)',
            fontWeight: 600
          }}>
            All steps completed!
          </div>
        )}
      </div>

      {/* Collected Data */}
      <div style={{ marginBottom: '20px', flex: 1, overflowY: 'auto' }}>
        <h4 style={{ margin: '0 0 10px 0', color: 'rgba(255, 255, 255, 0.9)' }}>Collected Data</h4>
        <div style={{ fontSize: '12px' }}>
          {Object.keys(sessionInfo.state.collected_data).length === 0 ? (
            <div style={{ color: 'rgba(156, 163, 175, 0.8)', fontStyle: 'italic' }}>No data collected yet</div>
          ) : (
            Object.entries(sessionInfo.state.collected_data).map(([key, value]) => (
              <div key={key} style={{
                marginBottom: '8px',
                padding: '8px',
                backgroundColor: 'rgba(51, 65, 85, 0.4)',
                borderRadius: '6px',
                border: '1px solid rgba(71, 85, 105, 0.4)',
                backdropFilter: 'blur(10px)'
              }}>
                <div style={{ fontWeight: 'bold', color: 'rgba(255, 255, 255, 0.9)', marginBottom: '2px' }}>
                  {key}:
                </div>
                <div style={{ color: 'rgba(156, 163, 175, 0.8)', wordBreak: 'break-word' }}>
                  {value || '(empty)'}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* User Input (Demo) */}
      {!sessionInfo.connected && (
        <div style={{ borderTop: '1px solid rgba(71, 85, 105, 0.3)', paddingTop: '15px' }}>
          <h4 style={{ margin: '0 0 10px 0', color: 'rgba(255, 255, 255, 0.9)' }}>Demo Input</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <textarea
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={currentStepInfo ? "Enter your response..." : "Intake completed"}
              style={{
                padding: '8px',
                borderRadius: '6px',
                border: '1px solid rgba(71, 85, 105, 0.4)',
                backgroundColor: 'rgba(51, 65, 85, 0.6)',
                color: 'white',
                fontSize: '12px',
                resize: 'none',
                height: '60px',
                backdropFilter: 'blur(10px)'
              }}
              disabled={!currentStepInfo}
            />
            <button
              onClick={handleSendMessage}
              disabled={!userInput.trim() || !currentStepInfo}
              style={{
                padding: '8px 16px',
                backgroundColor: currentStepInfo && userInput.trim() ? 'rgba(59, 130, 246, 0.8)' : 'rgba(107, 114, 128, 0.6)',
                color: 'white',
                border: '1px solid rgba(71, 85, 105, 0.4)',
                borderRadius: '6px',
                fontSize: '12px',
                cursor: currentStepInfo && userInput.trim() ? 'pointer' : 'not-allowed',
                backdropFilter: 'blur(10px)'
              }}
            >
              Send Response
            </button>
          </div>
          <div style={{ fontSize: '10px', color: 'rgba(156, 163, 175, 0.6)', marginTop: '8px' }}>
            This is demo mode. Connect to backend for real interaction.
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionPanel;
