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
  ConnectionLineType,
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

// Hoisted function component for the modal so it's available before usage
function NewQuestionModal({
  open,
  onClose,
  steps,
  insertAfter,
  setInsertAfter,
  prompt,
  setPrompt,
  inputKey,
  setInputKey,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  steps: { name: string; order_index: number }[];
  insertAfter: string;
  setInsertAfter: (v: string) => void;
  prompt: string;
  setPrompt: (v: string) => void;
  inputKey: string;
  setInputKey: (v: string) => void;
  onConfirm: () => void;
}) {
  if (!open) return null;
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
      <div style={{ width: 420, background: 'rgba(30,41,59,0.98)', border: '1px solid rgba(71,85,105,0.5)', borderRadius: 10, padding: 16 }}>
        <h3 style={{ marginTop: 0, color: 'white' }}>Insert New Question</h3>
        <div style={{ fontSize: 12, color: 'rgba(156,163,175,0.9)', marginBottom: 8 }}>Insert after</div>
        <select
          value={insertAfter}
          onChange={(e) => setInsertAfter(e.target.value)}
          style={{ width: '100%', padding: 8, borderRadius: 6, backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)' }}
        >
          <option value="">Select position...</option>
          {[...steps]
            .sort((a, b) => a.order_index - b.order_index)
            .map((s, idx) => (
              <option key={s.name} value={s.name}>
                {idx + 1}. {s.name}
              </option>
            ))}
          <option value="__END__">At the end (after all existing steps)</option>
        </select>
        <div style={{ fontSize: 12, color: 'rgba(156,163,175,0.9)', margin: '10px 0 6px' }}>Ask prompt</div>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Type the question the agent should ask"
          style={{ width: '100%', padding: 8, borderRadius: 6, backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)', height: 80 }}
        />
        <div style={{ fontSize: 12, color: 'rgba(156,163,175,0.9)', margin: '10px 0 6px' }}>Input key (optional)</div>
        <input
          value={inputKey}
          onChange={(e) => setInputKey(e.target.value)}
          placeholder="e.g., scene_photos"
          style={{ width: '100%', padding: 8, borderRadius: 6, backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)' }}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 12 }}>
          <button
            onClick={onClose}
            style={{ padding: '8px 12px', background: 'rgba(107,114,128,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)', borderRadius: 6 }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            style={{ padding: '8px 12px', background: 'rgba(34,197,94,0.85)', color: 'white', border: '1px solid rgba(34,197,94,0.4)', borderRadius: 6 }}
          >
            Add Step
          </button>
        </div>
      </div>
    </div>
  );
}

const IntakeFlowVisualizer: React.FC = () => {
  const { sessionInfo, steps, loading, error, startSession, sendMessage, insertStepAfter, updateStep, deleteStep } = useIntakeAPI();
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [showValues, setShowValues] = useState(false);
  const [editMode, setEditMode] = useState(false);

  // DnD: toolbox drag type
  const DND_NEW_QUESTION = 'application/flow-new-question';

  // Modal state for new question
  const [showNewQModal, setShowNewQModal] = useState(false);
  const [newQInsertAfter, setNewQInsertAfter] = useState<string>('');
  const [newQPrompt, setNewQPrompt] = useState<string>('');
  const [newQInputKey, setNewQInputKey] = useState<string>('');

  // Simple edit form state
  const [editStepName, setEditStepName] = useState<string>('');
  const [editPrompt, setEditPrompt] = useState<string>('');
  const [editNextName, setEditNextName] = useState<string>('');

  // Delete step handler
  const handleDeleteStep = useCallback(async (stepName: string) => {
    if (window.confirm(`Are you sure you want to delete the question "${stepName}"? This action cannot be undone.`)) {
      const success = await deleteStep({ name: stepName, flow_name: 'injury_intake_strict' });
      if (success) {
        console.log(`Successfully deleted step: ${stepName}`);
      }
    }
  }, [deleteStep]);

  // Generate nodes and edges from steps
  const generateFlowVisualization = useCallback((steps: IntakeStep[], currentState?: IntakeState) => {
    console.log('DEBUG Generating flow visualization:', { steps: steps.length, currentState });
    console.log('DEBUG editMode in generateFlowVisualization:', editMode);
    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];
    const collected = currentState?.collected_data ?? {};
    
    let yPosition = 50;
    const xPosition = 300; // Fixed x position for vertical layout
    const ySpacing = 180; // Vertical spacing between nodes

    // Create START node
    flowNodes.push({
      id: 'start',
      type: 'input',
      position: { x: xPosition, y: yPosition },
      data: {
        label: 'START',
        description: 'Begin Intake Process'
      },
      style: {
        backgroundColor: '#0f766e',
        color: 'white',
        fontWeight: 'bold',
        border: '2px solid rgba(10, 136, 90, 0.59)',
        backdropFilter: 'blur(6px)',
        borderRadius: '10px'
      }
    });

    yPosition += ySpacing;

    // Create nodes by following the next_name chain to reflect the true runtime flow
    console.log('DEBUG Processing steps (chain):', steps.map(s => s.name));
    const stepMap: Record<string, IntakeStep> = Object.fromEntries(steps.map(s => [s.name, s]));
    const allNames = new Set(steps.map(s => s.name));
    const pointed = new Set(steps.map(s => (s.next_name || '').trim()).filter(Boolean));
    // Prefer the step that no one points to; fallback to the first item
    let entryName: string = steps[0]?.name || '';
    for (const n of Array.from(allNames)) { if (!pointed.has(n)) { entryName = n; break; } }

    const visited = new Set<string>();
    let currentName: string | undefined = entryName;
    let prevAskIdForChain: string | null = null;
    let lastVisited: string | null = null;

    while (currentName && allNames.has(currentName) && !visited.has(currentName)) {
      const step = stepMap[currentName as string] as IntakeStep;
      visited.add(currentName);
      const isActive = currentState?.current_step === step.name;
      const isCompleted = currentState?.completed_steps.includes(step.name) || false;
      const askNodeId = `ask_${step.name}`;
      const askPosition = { x: xPosition, y: yPosition };

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
          collectedValue: currentState?.collected_data[step.input_key] || '',
          stepName: step.name,
          onDelete: editMode ? handleDeleteStep : undefined
        },
        style: {
          backgroundColor: '#27323f',
          color: 'rgba(255,255,255,0.92)',
          border: isActive
            ? '2px solid rgba(45,212,191,0.95)'
            : isCompleted
              ? '1px solid rgba(13,148,136,0.5)'
              : '1px solid rgba(255,255,255,0.12)',
          boxShadow: isActive
            ? '0 0 0 2px rgba(45,212,191,0.45), 0 0 10px rgba(45,212,191,0.45), 0 0 22px rgba(45,212,191,0.35), 0 0 40px rgba(45,212,191,0.25)'
            : '0 2px 0 rgba(0,0,0,0.25)',
          transition: 'box-shadow 150ms ease, border-color 150ms ease',
          backdropFilter: 'blur(4px)',
          borderRadius: '12px'
        }
      });

      // Connect from start or previous ask
      if (!prevAskIdForChain) {
        flowEdges.push({
          id: `start-${askNodeId}`,
          source: 'start',
          target: askNodeId,
          type: 'simplebezier',
          style: { stroke: 'rgba(20,184,166,0.9)', strokeWidth: 2 }
        });
      } else {
        const prevStepName = lastVisited as string; // not null if prevAskIdForChain exists
        const prevCompleted = currentState?.completed_steps.includes(prevStepName) || false;
        flowEdges.push({
          id: `${prevAskIdForChain}-${askNodeId}`,
          source: prevAskIdForChain,
          target: askNodeId,
          type: 'simplebezier',
          style: {
            stroke: prevCompleted ? 'rgba(20,184,166,0.7)' : 'rgba(255,255,255,0.18)',
            strokeWidth: prevCompleted ? 2 : 1
          }
        });
      }

      // Advance
      prevAskIdForChain = askNodeId;
      lastVisited = step.name;
      yPosition += ySpacing;
      currentName = (step.next_name || '').trim() || undefined;
    }

    // Append any orphan steps not connected by next_name chain (rare, shown after the main chain)
    for (const s of steps) {
      if (visited.has(s.name)) continue;
      const isActive = currentState?.current_step === s.name;
      const isCompleted = currentState?.completed_steps.includes(s.name) || false;
      const askNodeId = `ask_${s.name}`;
      const askPosition = { x: xPosition, y: yPosition };
      flowNodes.push({
        id: askNodeId,
        type: 'stepNode',
        position: askPosition,
        data: {
          label: `ASK: ${s.name}`,
          description: s.ask_prompt,
          stepType: 'ask',
          isActive,
          isCompleted,
          inputKey: s.input_key,
          collectedValue: currentState?.collected_data[s.input_key] || '',
          stepName: s.name,
          onDelete: editMode ? handleDeleteStep : undefined
        },
        style: {
          backgroundColor: '#27323f',
          color: 'rgba(255,255,255,0.92)',
          border: isActive
            ? '2px solid rgba(45,212,191,0.95)'
            : isCompleted
              ? '1px solid rgba(13,148,136,0.5)'
              : '1px solid rgba(255,255,255,0.12)',
          boxShadow: isActive
            ? '0 0 0 2px rgba(45,212,191,0.45), 0 0 10px rgba(45,212,191,0.45), 0 0 22px rgba(45,212,191,0.35), 0 0 40px rgba(45,212,191,0.25)'
            : '0 2px 0 rgba(0,0,0,0.25)',
          transition: 'box-shadow 150ms ease, border-color 150ms ease',
          backdropFilter: 'blur(4px)',
          borderRadius: '12px'
        }
      });
      // Link from previous placed node
      if (prevAskIdForChain) {
        const prevCompleted = lastVisited ? (currentState?.completed_steps.includes(lastVisited) || false) : false;
        flowEdges.push({
          id: `${prevAskIdForChain}-${askNodeId}`,
          source: prevAskIdForChain,
          target: askNodeId,
          type: 'simplebezier',
          style: {
            stroke: prevCompleted ? 'rgba(20,184,166,0.7)' : 'rgba(255,255,255,0.18)',
            strokeWidth: prevCompleted ? 2 : 1
          }
        });
      } else {
        flowEdges.push({
          id: `start-${askNodeId}`,
          source: 'start',
          target: askNodeId,
          type: 'simplebezier',
          style: { stroke: 'rgba(20,184,166,0.9)', strokeWidth: 2 }
        });
      }
      prevAskIdForChain = askNodeId;
      lastVisited = s.name;
      yPosition += ySpacing;
    }

    // Create END node
    const lastStep = lastVisited ? stepMap[lastVisited] : steps[steps.length - 1];
    const endNodeId = 'end';
    const isCompleted = currentState?.current_step === 'completed' || currentState?.session_status === 'completed';
    
    flowNodes.push({
      id: endNodeId,
      type: 'output',
      position: { x: xPosition, y: yPosition },
      data: { 
        label: isCompleted ? ' COMPLETED' : 'END',
        description: isCompleted ? 'Intake Successfully Completed!' : 'Intake Complete'
      },
      style: { 
        backgroundColor: isCompleted ? '#14b8a6' : '#111827',
        color: 'white',
        fontWeight: 'bold',
        border: isCompleted ? '3px solid #0d9488' : '1px solid rgba(255,255,255,0.08)',
        backdropFilter: 'blur(6px)',
        borderRadius: '12px'
      }
    });

    // Edge to END
    if (lastStep) {
      const lastAskId = `ask_${lastStep.name}`;
      flowEdges.push({
        id: `${lastAskId}-${endNodeId}`,
        source: lastAskId,
        target: endNodeId,
        type: 'simplebezier',
        animated: isCompleted,
        style: { 
          stroke: isCompleted ? 'rgba(20,184,166,0.95)' : 'rgba(255,255,255,0.18)',
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
  }, [showValues, editMode, handleDeleteStep]);

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

  // Drag handlers
  const onDragStartNewQuestion = (event: React.DragEvent<HTMLDivElement>) => {
    event.dataTransfer.setData(DND_NEW_QUESTION, '1');
    event.dataTransfer.effectAllowed = 'move';
  };

  const onDragOverCanvas = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const findNearestAskNode = useCallback((pos: { x: number; y: number }): string | null => {
    let bestId: string | null = null;
    let bestDist = Number.POSITIVE_INFINITY;
    for (const n of nodes as Node<any>[]) {
      if (n.type !== 'stepNode') continue;
      const data = n.data as any;
      if (!data || data.stepType !== 'ask') continue;
      const dx = (n.position?.x ?? 0) - pos.x;
      const dy = (n.position?.y ?? 0) - pos.y;
      const d = dx * dx + dy * dy;
      if (d < bestDist) { bestDist = d; bestId = n.id; }
    }
    if (!bestId) return null;
    // id format is ask_<stepName>
    if (bestId.startsWith('ask_')) return bestId.substring(4);
    return null;
  }, [nodes]);

  const onDropCanvas = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const hasNewQ = event.dataTransfer.getData(DND_NEW_QUESTION);
    if (!hasNewQ) return;
    // Default insert_after: current step if available, otherwise last step, otherwise first
    const current = sessionInfo?.state?.current_step;
    const fallback = steps.length > 0 ? (steps[steps.length - 1].name || steps[0].name) : '';
    const initial = current || fallback;
    setNewQInsertAfter(initial);
    setNewQPrompt('');
    setNewQInputKey('');
    setShowNewQModal(true);
  }, [sessionInfo?.state?.current_step, steps]);

  const slugify = (s: string) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'step';

  const handleConfirmNewQuestion = async () => {
    if (!newQPrompt.trim() || !newQInsertAfter) {
      setShowNewQModal(false);
      return;
    }
    
    // Handle special case for inserting at the end
    let insertAfterStep = newQInsertAfter;
    if (newQInsertAfter === '__END__') {
      // Find the last step (highest order_index)
      const lastStep = steps.reduce((prev, current) => 
        (prev.order_index > current.order_index) ? prev : current
      );
      insertAfterStep = lastStep.name;
    }
    
    const ok = await insertStepAfter({
      insert_after: insertAfterStep,
      ask_prompt: newQPrompt.trim(),
      name: undefined,
      input_key: newQInputKey.trim() ? slugify(newQInputKey) : undefined,
      validate_regex: null,
      system_prompt: 'You are Michelle, an empathetic intake specialist.',
      flow_name: 'injury_intake_strict',
    });
    setShowNewQModal(false);
    if (ok) {
      // Optionally, auto-select the edited step name
      setEditStepName('');
      setEditPrompt('');
    }
  };

  const handleUpdateStep = async () => {
    if (!editStepName) return;
    await updateStep({ 
      name: editStepName, 
      ask_prompt: editPrompt.trim() || undefined, 
      next_name: editNextName === '__END__' ? null : (editNextName || null),
      flow_name: 'injury_intake_strict' 
    });
    setEditPrompt('');
  };

  // When selecting a step to edit, preload its current prompt and next_name
  useEffect(() => {
    const s = steps.find(x => x.name === editStepName);
    if (s) {
      setEditPrompt(s.ask_prompt || '');
      setEditNextName((s.next_name || '')); // '' means END for our select
    } else {
      setEditPrompt('');
      setEditNextName('');
    }
  }, [editStepName, steps]);


  return (
    <div style={{ display: 'flex', height: '100%', backgroundColor: '#000000' }}>
      <div style={{ flex: 1 }}>
        {/* Controls */}
        <div style={{ 
          padding: '12px 16px', 
          backgroundColor: '#0b0f13',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          backdropFilter: 'blur(6px)'
        }}>
              <button 
                onClick={() => startSession(false)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#262626',
                  color: 'white',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(6px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Start Text Session
              </button>
              <button 
                onClick={() => setEditMode(!editMode)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: editMode ? 'rgba(239, 68, 68, 0.8)' : '#262626',
                  color: 'white',
                  border: editMode ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(6px)',
                  transition: 'all 0.2s ease'
                }}
                title={editMode ? 'Exit edit mode' : 'Enter edit mode to delete questions'}
              >
                {editMode ? '✓ Exit Edit' : 'Edit Mode'}
              </button>
              <button 
                onClick={() => startSession(true)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#0f766e',
                  color: 'white',
                  border: '1px solid rgba(13,148,136,0.8)',
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(6px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Start Voice Session
              </button>
              <button 
                onClick={() => setShowValues(!showValues)}
                style={{
                  padding: '10px 20px',
                  backgroundColor: showValues ? 'rgba(239, 68, 68, 0.85)' : '#262626',
                  color: 'white',
                  border: `1px solid ${showValues ? 'rgba(239, 68, 68, 0.5)' : 'rgba(255,255,255,0.08)'}`,
                  borderRadius: '8px',
                  cursor: 'pointer',
                  marginRight: '12px',
                  backdropFilter: 'blur(6px)',
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
                  backgroundColor: '#111827',
                  color: 'white',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: '6px',
                  backdropFilter: 'blur(4px)',
                  minWidth: '200px'
                }}
              />
              <button 
                type="submit"
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#0f766e',
                  color: 'white',
                  border: '1px solid rgba(13,148,136,0.8)',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  backdropFilter: 'blur(4px)',
                  transition: 'all 0.2s ease'
                }}
              >
                Send
              </button>
            </form>
          )}
        </div>
        
        {/* Flow Diagram */}
        <div style={{ height: 'calc(100% - 80px)', backgroundColor: '#000000' }}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            connectionMode={ConnectionMode.Loose}
            connectionLineType={ConnectionLineType.SimpleBezier}
            defaultEdgeOptions={{
              type: 'simplebezier',
              style: { stroke: 'rgba(71, 85, 105, 0.6)', strokeWidth: 1.5, strokeLinecap: 'round' }
            }}
            onDrop={onDropCanvas}
            onDragOver={onDragOverCanvas}
            fitView
            attributionPosition="bottom-left"
            style={{ backgroundColor: '#000000' }}
          >
            <Background 
              variant={'dots' as any} 
              gap={22} 
              size={1.2} 
              color="rgba(255,255,255,0.06)"
            />
            <Controls />
          </ReactFlow>
        </div>
      </div>
      
      {/* Side Panel */}
      <div style={{ 
        width: 350, 
        borderLeft: '1px solid rgba(255,255,255,0.06)', 
        backgroundColor: '#0b0f13',
        backdropFilter: 'blur(6px)',
        height: '100%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Flow Toolbox (pre-session) */}
        <div style={{ padding: '16px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
          <h4 style={{ margin: '0 0 10px 0', color: 'rgba(255,255,255,0.9)' }}>Flow Toolbox</h4>
          <div
            draggable
            onDragStart={onDragStartNewQuestion}
            style={{
              padding: '10px',
              backgroundColor: 'rgba(59, 130, 246, 0.15)',
              border: '1px dashed rgba(59, 130, 246, 0.5)',
              borderRadius: '8px',
              color: 'rgba(255,255,255,0.9)',
              cursor: 'grab',
              userSelect: 'none',
              marginBottom: '12px'
            }}
            title="Drag onto the canvas near an ASK node to insert a new question after it"
          >
            + New Step (drag to insert)
          </div>

          {/* Simple editor (optional; pre-session) */}
          <div style={{ marginTop: '12px' }}>
            <div style={{ fontSize: 12, color: 'rgba(156,163,175,0.8)', marginBottom: 6 }}>Edit existing flow</div>
            <select
              value={editStepName}
              onChange={(e) => setEditStepName(e.target.value)}
              style={{
                width: '100%', padding: 8, borderRadius: 6,
                backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)'
              }}
            >
              <option value="">Select step…</option>
              {[...steps]
                .sort((a, b) => a.order_index - b.order_index)
                .map((s, idx) => (
                  <option key={s.name} value={s.name}>{idx + 1}. {s.name}</option>
                ))}
            </select>
            <textarea
              value={editPrompt}
              onChange={(e) => setEditPrompt(e.target.value)}
              placeholder="New ask prompt"
              style={{
                marginTop: 8, width: '100%', padding: 8, borderRadius: 6,
                backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)', height: 60
              }}
            />
            <div style={{ fontSize: 12, color: 'rgba(156,163,175,0.8)', margin: '8px 0 6px' }}>Next step after this</div>
            <select
              value={editNextName || '__END__'}
              onChange={(e) => setEditNextName(e.target.value)}
              style={{
                width: '100%', padding: 8, borderRadius: 6,
                backgroundColor: 'rgba(51,65,85,0.6)', color: 'white', border: '1px solid rgba(71,85,105,0.4)'
              }}
              disabled={!editStepName}
            >
              <option value="__END__">END (complete flow)</option>
              {[...steps]
                .sort((a, b) => a.order_index - b.order_index)
                .filter(s => s.name !== editStepName)
                .map((s) => (
                  <option key={s.name} value={s.name}>{s.name}</option>
                ))}
            </select>
            <button
              onClick={handleUpdateStep}
              disabled={!editStepName}
              style={{
                marginTop: 8,
                padding: '8px 12px',
                borderRadius: 6,
                backgroundColor: (!editStepName) ? 'rgba(107,114,128,0.6)' : 'rgba(34,197,94,0.8)',
                color: 'white',
                border: '1px solid rgba(71,85,105,0.4)',
                cursor: (!editStepName) ? 'not-allowed' : 'pointer'
              }}
            >
              Save Step
            </button>
          </div>
        </div>

        {/* Session Panel */}
        {sessionInfo && (
          <div style={{ padding: '16px', flexShrink: 0 }}>
            <SessionPanel sessionInfo={sessionInfo} steps={steps} />
          </div>
        )}
      </div>

      {/* Modal for new question */}
      <NewQuestionModal
        open={showNewQModal}
        onClose={() => setShowNewQModal(false)}
        steps={steps.map(s => ({ name: s.name, order_index: s.order_index }))}
        insertAfter={newQInsertAfter}
        setInsertAfter={setNewQInsertAfter}
        prompt={newQPrompt}
        setPrompt={setNewQPrompt}
        inputKey={newQInputKey}
        setInputKey={setNewQInputKey}
        onConfirm={handleConfirmNewQuestion}
      />
    </div>
  );
};
export default IntakeFlowVisualizer;