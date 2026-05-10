import React, { useState } from 'react';
import Uploader from './components/Uploader';
import Chat from './components/Chat';

function App() {
  const [documentId, setDocumentId] = useState(null);
  const [fileName, setFileName] = useState('');

  const handleUploadSuccess = (id, name) => {
    setDocumentId(id);
    setFileName(name);
  };

  const resetSession = () => {
    setDocumentId(null);
    setFileName('');
  };

  return (
    <div className="app-container">
      <header className="header">
        <h1>Juris AI</h1>
        <p>Highly Accurate Legal Document Intelligence — Powered by PageIndex</p>
      </header>
      
      {!documentId ? (
        <Uploader onUploadSuccess={handleUploadSuccess} />
      ) : (
        <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
          <div style={{ padding: '1rem', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: 'var(--accent-color)', fontWeight: 600 }}>Analyzing: {fileName}</span>
            <button 
              onClick={resetSession}
              style={{ background: 'transparent', color: 'var(--text-muted)', border: 'none', cursor: 'pointer', fontSize: '0.9rem' }}
            >
              Start New Document
            </button>
          </div>
          <Chat documentId={documentId} />
        </div>
      )}
    </div>
  );
}

export default App;
