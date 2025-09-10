import React from 'react';
import { Handle, Position, NodeProps } from 'reactflow';

interface StepNodeData {
  label: string;
  description: string;
  stepType: 'ask' | 'store';
  isActive: boolean;
  isCompleted: boolean;
  inputKey: string;
  collectedValue: string;
  icon?: string;
  stepName?: string;
  onDelete?: (stepName: string) => void;
}

const StepNode: React.FC<NodeProps<StepNodeData>> = ({ data }) => {
  const { label, description, stepType, isActive, isCompleted, inputKey, collectedValue, icon, stepName, onDelete } = data;

  const getStatusIcon = () => {
    if (isCompleted) return '✓';
    if (isActive) return '●';
    return '○';
  };

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '12px',
        minWidth: '220px',
        maxWidth: '280px',
        fontSize: '12px',
        boxShadow: '0 6px 24px rgba(0,0,0,0.25)'
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: 'rgba(255,255,255,0.5)' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
        <div style={{ marginRight: '8px', fontSize: '16px', color: '#9ca3af', display: 'flex', alignItems: 'center' }}>
          {stepType === 'ask' ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M13.5 4.06c0-1.336-1.616-2.005-2.56-1.06l-4.5 4.5H4.508c-1.141 0-2.318.664-2.66 1.905A9.76 9.76 0 001.5 12c0 .898.121 1.768.35 2.595.341 1.24 1.518 1.905 2.659 1.905h1.93l4.5 4.5c.945.945 2.561.276 2.561-1.06V4.06zM18.584 5.106a.75.75 0 011.06 0 11.5 11.5 0 010 16.27.75.75 0 11-1.06-1.061 10 10 0 000-14.148.75.75 0 010-1.06z" />
              <path d="M15.932 7.757a.75.75 0 011.061 0 6.5 6.5 0 010 9.185.75.75 0 01-1.06-1.06 5 5 0 000-7.07.75.75 0 010-1.055z" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21 6.375c0 2.692-4.03 4.875-9 4.875S3 9.067 3 6.375 7.03 1.5 12 1.5s9 2.183 9 4.875z" />
              <path d="M12 12.75c2.685 0 5.19-.586 7.078-1.609a8.283 8.283 0 001.897-1.384c.016.121.025.244.025.368C21 12.817 16.97 15 12 15s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.285 8.285 0 001.897 1.384C6.809 12.164 9.315 12.75 12 12.75z" />
              <path d="M12 16.5c2.685 0 5.19-.586 7.078-1.609a8.282 8.282 0 001.897-1.384c.016.121.025.244.025.368 0 2.692-4.03 4.875-9 4.875s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.284 8.284 0 001.897 1.384C6.809 15.914 9.315 16.5 12 16.5z" />
              <path d="M12 20.25c2.685 0 5.19-.586 7.078-1.609a8.282 8.282 0 001.897-1.384c.016.121.025.244.025.368 0 2.692-4.03 4.875-9 4.875s-9-2.183-9-4.875c0-.124.009-.247.025-.368a8.284 8.284 0 001.897 1.384C6.809 19.664 9.315 20.25 12 20.25z" />
            </svg>
          )}
        </div>
        <strong style={{ fontSize: '12px', flex: 1, color: 'rgba(255,255,255,0.95)' }}>
          {description}
        </strong>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {stepType === 'ask' && stepName && onDelete && (
            <button
              onClick={() => onDelete(stepName)}
              style={{
                background: 'rgba(239, 68, 68, 0.9)',
                border: '1px solid rgba(239, 68, 68, 0.8)',
                borderRadius: '4px',
                color: 'white',
                fontSize: '14px',
                fontWeight: 'bold',
                padding: '4px 8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
                minWidth: '24px',
                minHeight: '24px',
                zIndex: 10
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 1)';
                e.currentTarget.style.transform = 'scale(1.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(239, 68, 68, 0.9)';
                e.currentTarget.style.transform = 'scale(1)';
              }}
              title="Delete this question"
            >
              ×
            </button>
          )}
          <span style={{ fontSize: '16px', color: 'rgba(255,255,255,0.7)' }}>
            {getStatusIcon()}
          </span>
        </div>
      </div>

      {false && (
        <div />
      )}

      {collectedValue && (
        <div style={{
          marginTop: '8px',
          padding: '8px 10px',
          backgroundColor: 'rgba(14, 182, 138, 0.37)',
          borderRadius: '8px',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.95)',
          wordBreak: 'break-word',
          border: '1px solid rgba(15, 182, 140, 0.41)'
        }}>
          <span style={{ opacity: 0.9 }}>Response: </span>
          {collectedValue.length > 48 ? `${collectedValue.substring(0, 48)}...` : collectedValue}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ background: 'rgba(255,255,255,0.5)' }} />
    </div>
  );
};

export default StepNode;
