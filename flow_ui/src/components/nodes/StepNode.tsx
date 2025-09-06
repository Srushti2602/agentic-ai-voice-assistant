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
}

const StepNode: React.FC<NodeProps<StepNodeData>> = ({ data }) => {
  const { label, description, stepType, isActive, isCompleted, inputKey, collectedValue } = data;

  const getStatusIcon = () => {
    if (isCompleted) return '✓';
    if (isActive) return '●';
    return '○';
  };

  return (
    <div
      style={{
        padding: '12px',
        borderRadius: '8px',
        minWidth: '200px',
        maxWidth: '250px',
        fontSize: '12px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#555' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '8px' }}>
        <strong style={{ fontSize: '12px', flex: 1 }}>
          {stepType === 'ask' ? description : `Store: ${inputKey}`}
        </strong>
        <span style={{ marginLeft: '8px', fontSize: '16px' }}>
          {getStatusIcon()}
        </span>
      </div>

      {stepType === 'store' && (
        <div style={{ 
          fontSize: '10px', 
          color: isActive || isCompleted ? 'rgba(255,255,255,0.7)' : '#888',
          marginBottom: '6px',
          fontStyle: 'italic'
        }}>
          Saves to database
        </div>
      )}

      {collectedValue && (
        <div style={{
          marginTop: '6px',
          padding: '6px 8px',
          backgroundColor: 'rgba(34, 197, 94, 0.2)',
          borderRadius: '6px',
          fontSize: '10px',
          color: 'rgba(34, 197, 94, 0.9)',
          wordBreak: 'break-word',
          border: '1px solid rgba(34, 197, 94, 0.3)'
        }}>
          {collectedValue.length > 40 ? `${collectedValue.substring(0, 40)}...` : collectedValue}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ background: '#555' }} />
    </div>
  );
};

export default StepNode;
