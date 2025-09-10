import React from 'react';
import IntakeFlowVisualizer from './components/IntakeFlowVisualizer';
import './App.css';

function App() {
  return (
    <div className="App" style={{ backgroundColor: '#000000', minHeight: '100vh' }}>
      <header className="App-header" style={{ 
        padding: '1rem', 
        backgroundColor: '#0b0f13',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(6px)'
      }}>
        <h1 style={{ color: 'rgba(255, 255, 255, 0.95)', margin: '0 0 0.5rem 0' }}>Injury Record Helpline</h1>
      </header>
      <main style={{ height: 'calc(100vh - 120px)' }}>
        <IntakeFlowVisualizer />
      </main>
    </div>
  );
}

export default App;
