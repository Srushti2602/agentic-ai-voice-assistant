import React from 'react';
import IntakeFlowVisualizer from './components/IntakeFlowVisualizer';
import './App.css';

function App() {
  return (
    <div className="App" style={{ backgroundColor: '#0f172a', minHeight: '100vh' }}>
      <header className="App-header" style={{ 
        padding: '1rem', 
        backgroundColor: 'rgba(30, 41, 59, 0.95)', 
        borderBottom: '1px solid rgba(71, 85, 105, 0.3)',
        backdropFilter: 'blur(10px)'
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
