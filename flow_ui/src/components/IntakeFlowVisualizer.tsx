import React, { useEffect, useCallback, useState } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  ConnectionMode,
} from 'reactflow';
import 'reactflow/dist/style.css';
import { IntakeStep, IntakeState } from '../types/IntakeTypes';
import StepNode from './nodes/StepNode';
import SessionPanel from './SessionPanel';
import { useIntakeAPI } from '../hooks/useIntakeAPI';

// Debounce function to prevent excessive re-renders
function debounce<F extends (...a: any[]) => void>(fn: F, ms = 100) {
  let t: any; 
  return (...a: any[]) => { 
    clearTimeout(t); 
    t = setTimeout(() => fn(...a), ms); 
  };
}

// Custom node types
const nodeTypes = {
  stepNode: StepNode,
};

const IntakeFlowVisualizer: React.FC = () => {
  const { sessionInfo, steps, loading, error, startSession, sendMessage } = useIntakeAPI();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [showValues, setShowValues] = useState(false);

  // Generate nodes and edges from steps
  const generateFlowVisualization = useCallback((steps: IntakeStep[], currentState?: IntakeState) => {
    console.log('DEBUG Generating flow visualization:', { steps: steps.length, currentState });
    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];
    const collected = currentState?.collected_data ?? {};
    
    let yPosition = 50;
    const xSpacing = 300;
    const ySpacing = 200;

    // Create START node
    flowNodes.push({
      id: 'start',
      type: 'input',
      position: { x: 50, y: yPosition },
      data: {
        label: 'START',
        description: 'Begin Intake Process'
      },
      style: {
        backgroundColor: 'rgba(34, 197, 94, 0.9)',
        color: 'white',
        fontWeight: 'bold',
        border: '2px solid rgba(34, 197, 94, 0.6)',
        backdropFilter: 'blur(10px)',
        borderRadius: '8px'
      }
    });

    // Create nodes for each step (ask + store pattern from your LangGraph)
    console.log('DEBUG Processing steps:', steps.map(s => s.name));
    steps.forEach((step, index) => {
      console.log(`DEBUG Creating nodes for step ${index}:`, step.name);
      const isActive = currentState?.current_step === step.name;
      const isCompleted = currentState?.completed_steps.includes(step.name) || false;
      
      // Ask node
      const askNodeId = `ask_${step.name}`;
      const askPosition = { x: 100 + (index % 3) * xSpacing, y: yPosition + Math.floor(index / 3) * ySpacing };
      console.log(`DEBUG Ask node position for ${step.name}:`, askPosition);
      flowNodes.push({
        id: askNodeId,
        type: 'stepNode',
        position: askPosition,
        data: {
          label: `ASK: ${step.name}`,
          description: step.ask_prompt,
          stepType: 'ask',
          isActive,
          isCompleted,
          inputKey: step.input_key,
          collectedValue: currentState?.collected_data[step.input_key] || ''
        },
        style: {
          backgroundColor: isActive ? 'rgba(59, 130, 246, 0.9)' : isCompleted ? 'rgba(34, 197, 94, 0.8)' : 'rgba(51, 65, 85, 0.8)',
          color: 'white',
          border: isActive ? '2px solid rgba(59, 130, 246, 1)' : isCompleted ? '1px solid rgba(34, 197, 94, 0.6)' : '1px solid rgba(71, 85, 105, 0.4)',
          backdropFilter: 'blur(10px)',
          borderRadius: '8px'
        }
      });

      // Store node
      const storeNodeId = `store_${step.name}`;
      const storePosition = { x: 100 + (index % 3) * xSpacing, y: yPosition + Math.floor(index / 3) * ySpacing + 120 };
      console.log(`DEBUG Store node position for ${step.name}:`, storePosition);
      flowNodes.push({
        id: storeNodeId,
        type: 'stepNode',
        position: storePosition,
        data: {
          label: `STORE: ${step.name}`,
          description: `Store ${step.input_key} in database`,
          stepType: 'store',
          isActive: false,
          isCompleted,
          inputKey: step.input_key,
          collectedValue: showValues ? collected[step.input_key] || '' : ''
        },
        style: {
          backgroundColor: isCompleted ? 'rgba(139, 92, 246, 0.8)' : 'rgba(71, 85, 105, 0.6)',
          color: 'white',
          border: isCompleted ? '1px solid rgba(139, 92, 246, 0.6)' : '1px solid rgba(71, 85, 105, 0.4)',
          backdropFilter: 'blur(10px)',
          borderRadius: '8px'
        }
      });

      // Edge from ask to store
      flowEdges.push({
        id: `${askNodeId}-${storeNodeId}`,
        source: askNodeId,
        target: storeNodeId,
        type: 'smoothstep',
        animated: isActive,
        style: { 
          stroke: isCompleted ? 'rgba(34, 197, 94, 0.8)' : 'rgba(71, 85, 105, 0.6)',
          strokeWidth: isCompleted ? 2 : 1
        }
      });

      // Edge from previous step or start
      if (index === 0) {
        flowEdges.push({
          id: `start-${askNodeId}`,
          source: 'start',
          target: askNodeId,
          type: 'smoothstep',
          style: { 
            stroke: 'rgba(34, 197, 94, 0.8)',
            strokeWidth: 2
          }
        });
      } else {
        const prevStoreId = `store_${steps[index - 1].name}`;
        const prevCompleted = currentState?.completed_steps.includes(steps[index - 1].name) || false;
        flowEdges.push({
          id: `${prevStoreId}-${askNodeId}`,
          source: prevStoreId,
          target: askNodeId,
          type: 'smoothstep',
          style: { 
            stroke: prevCompleted ? 'rgba(34, 197, 94, 0.8)' : 'rgba(71, 85, 105, 0.6)',
            strokeWidth: prevCompleted ? 2 : 1
          }
        });
      }
    });

    // Create END node
    const lastStep = steps[steps.length - 1];
    const endNodeId = 'end';
    const isCompleted = currentState?.current_step === 'completed' || currentState?.session_status === 'completed';
    
    flowNodes.push({
      id: endNodeId,
      type: 'output',
      position: { x: 200 + ((steps.length - 1) % 3) * xSpacing, y: yPosition + Math.floor((steps.length - 1) / 3) * ySpacing + 160 },
      data: { 
        label: isCompleted ? '🎉 COMPLETED' : 'END',
        description: isCompleted ? 'Intake Successfully Completed!' : 'Intake Complete'
      },
      style: { 
        backgroundColor: isCompleted ? 'rgba(34, 197, 94, 0.9)' : 'rgba(107, 114, 128, 0.8)',
        color: 'white',
        fontWeight: 'bold',
        border: isCompleted ? '3px solid rgba(34, 197, 94, 0.6)' : '1px solid rgba(107, 114, 128, 0.4)',
        backdropFilter: 'blur(10px)',
        borderRadius: '8px'
      }
    });

    // Edge to END
    if (lastStep) {
      flowEdges.push({
        id: `store_${lastStep.name}-${endNodeId}`,
        source: `store_${lastStep.name}`,
        target: endNodeId,
        type: 'smoothstep',
        animated: isCompleted,
        style: { 
          stroke: isCompleted ? 'rgba(34, 197, 94, 0.9)' : 'rgba(71, 85, 105, 0.6)',
          strokeWidth: isCompleted ? 3 : 1
        }
      });
    }

    console.log('DEBUG Generated visualization:', { 
      totalNodes: flowNodes.length, 
      totalEdges: flowEdges.length,
      nodeIds: flowNodes.map(n => n.id)
    });
    return { nodes: flowNodes, edges: flowEdges };
  }, [showValues]);

  // Debounced graph application to prevent excessive re-renders
  const applyGraph = useCallback(
    debounce((steps: IntakeStep[], st?: IntakeState) => {
      const { nodes: ns, edges: es } = generateFlowVisualization(steps, st);
      setNodes(ns);
      setEdges(es);
    }, 80),
    [generateFlowVisualization, setNodes, setEdges]
  );

  // Update flow visualization when steps or session state changes
  useEffect(() => {
    applyGraph(steps, sessionInfo?.state);
  }, [steps, sessionInfo?.state, applyGraph]);

  // Suppress ResizeObserver errors
  useEffect(() => {
    const resizeObserverErrDiv = document.getElementById('webpack-dev-server-client-overlay-div');
    const resizeObserverErr = document.getElementById('webpack-dev-server-client-overlay');
    if (resizeObserverErr) {
      resizeObserverErr.setAttribute('style', 'display: none');
    }
    if (resizeObserverErrDiv) {
      resizeObserverErrDiv.setAttribute('style', 'display: none');
    }
  }, []);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  return (
    <div style={{ display: 'flex', height: '100%', backgroundColor: '#1e293b' }}>
      <div style={{ flex: 1 }}>
        {/* Controls */}
        <div style={{ 
          padding: '12px 16px', 
          backgroundColor: 'rgba(30, 41, 59, 0.95)', 
          borderBottom: '1px solid rgba(71, 85, 105, 0.3)',
          backdropFilter: 'blur(10px)'
        }}>
              <button 
                onClick={() => startSession(false)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: 'rgba(59, 130, 246, 0.8)',
                  color: 'white',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(10px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Start Text Session
              </button>
              <button 
                onClick={() => startSession(true)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: 'rgba(34, 197, 94, 0.8)',
                  color: 'white',
                  border: '1px solid rgba(34, 197, 94, 0.4)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(10px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Start Voice Session
              </button>
              <button 
                onClick={() => setShowValues(!showValues)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: showValues ? 'rgba(239, 68, 68, 0.8)' : 'rgba(107, 114, 128, 0.8)',
                  color: 'white',
                  border: `1px solid ${showValues ? 'rgba(239, 68, 68, 0.4)' : 'rgba(107, 114, 128, 0.4)'}`,
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(10px)',
                  transition: 'all 0.2s ease'
                }}
              >
                {showValues ? 'Hide Values' : 'Show Values'}
              </button>
          {sessionInfo && (
            <form 
              onSubmit={(e) => { 
                e.preventDefault(); 
                const form = e.target as HTMLFormElement;
                const input = form.msg as HTMLInputElement;
                const value = input.value;
                if (value.trim()) {
                  sendMessage(value); 
                  form.reset(); 
                }
              }}
              style={{ display: 'inline-flex', gap: '8px', alignItems: 'center', marginLeft: '12px' }}
            >
              <input 
                name="msg" 
                placeholder="Say something..." 
                style={{
                  padding: '8px 12px',
                  backgroundColor: 'rgba(51, 65, 85, 0.8)',
                  color: 'white',
                  border: '1px solid rgba(71, 85, 105, 0.4)',
                  borderRadius: '6px',
                  backdropFilter: 'blur(10px)',
                  minWidth: '200px'
                }}
              />
              <button 
                type="submit"
                style={{
                  padding: '8px 16px',
                  backgroundColor: 'rgba(59, 130, 246, 0.8)',
                  color: 'white',
                  border: '1px solid rgba(59, 130, 246, 0.4)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  backdropFilter: 'blur(10px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Send
              </button>
            </form>
          )}
        </div>
        
        {/* Flow Diagram */}
        <div style={{ height: 'calc(100% - 80px)', backgroundColor: '#0f172a' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            connectionMode={ConnectionMode.Loose}
            fitView
            attributionPosition="bottom-left"
            style={{ backgroundColor: '#0f172a' }}
          >
            <Background 
              variant={'dots' as any} 
              gap={20} 
              size={1.5} 
              color="rgba(71, 85, 105, 0.3)"
            />
            <Controls />
          </ReactFlow>
        </div>
      </div>
      
      {/* Side Panel */}
      <div style={{ 
        width: 350, 
        borderLeft: '1px solid rgba(71, 85, 105, 0.3)', 
        backgroundColor: 'rgba(30, 41, 59, 0.95)',
        backdropFilter: 'blur(10px)'
      }}>
        <SessionPanel sessionInfo={sessionInfo} steps={steps} />
      </div>
    </div>
  );
};

export default IntakeFlowVisualizer;