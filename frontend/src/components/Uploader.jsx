import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Loader } from 'lucide-react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Uploader = ({ onUploadSuccess }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = () => {
    setIsDragOver(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = e.dataTransfer.files;
    if (files.length) {
      processFile(files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files.length) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = async (file) => {
    if (file.type !== 'application/pdf') {
      setError('Please upload a valid PDF document.');
      return;
    }
    
    setError('');
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);

    try {
      // Ensure backend URL is correct (using default FastAPI port)
      const res = await axios.post(`${API_URL}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      // Response contains document_id
      onUploadSuccess(res.data.document_id, file.name);
    } catch (err) {
      console.error(err);
      setError(err.response?.data?.detail || 'An error occurred during upload. Is the backend running?');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div 
      className={`glass-panel uploader-container ${isDragOver ? 'drag-over' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => !isUploading && fileInputRef.current?.click()}
    >
      <input 
        type="file" 
        accept=".pdf" 
        style={{ display: 'none' }} 
        ref={fileInputRef}
        onChange={handleFileChange}
      />
      
      {isUploading ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Loader size={48} className="upload-icon" style={{ animation: 'spin 2s linear infinite' }} />
          <h3 style={{ margin: '1rem 0' }}>Analyzing Document Structure...</h3>
          <p style={{ color: 'var(--text-muted)' }}>Building Vectorless PageIndex</p>
        </div>
      ) : (
        <>
          <UploadCloud size={64} className="upload-icon" />
          <h2 style={{ marginBottom: '1rem' }}>Upload Legal Document</h2>
          <p style={{ color: 'var(--text-muted)' }}>Drag and drop your PDF contract or agreement here, or click to browse files.</p>
          {error && <p style={{ color: '#ef4444', marginTop: '1rem', fontWeight: 600 }}>{error}</p>}
          <button className="upload-button">Select File</button>
        </>
      )}
    </div>
  );
};

export default Uploader;
