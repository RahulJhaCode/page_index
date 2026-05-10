import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText } from 'lucide-react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const Chat = ({ documentId }) => {
  const [messages, setMessages] = useState([
    { id: 1, role: 'bot', text: 'Document analyzed and indexed. What specific legal details would you like to extract?' }
  ]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isTyping]);

  const handleSend = async (e) => {
    e?.preventDefault();
    if (!input.trim()) return;

    const userMessage = { id: Date.now(), role: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await axios.post(`${API_URL}/chat`, {
        document_id: documentId,
        query: userMessage.text
      });

      const botMessage = {
        id: Date.now() + 1,
        role: 'bot',
        text: res.data.answer,
        citedPages: res.data.cited_pages
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error(err);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'bot',
        text: 'Sorry, I encountered an error communicating with the interpretation engine.'
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div className="chat-messages" ref={scrollRef}>
        {messages.map(msg => (
          <div key={msg.id} className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-bot'}`}>
            <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
            
            {msg.citedPages && msg.citedPages.length > 0 && (
              <div className="cited-pages">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sources:</span>
                {msg.citedPages.map(page => (
                  <span key={page} className="badge">
                    <FileText size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-bottom' }} />
                    Page(s) {page}
                  </span>
                ))}
              </div>
            )}
            {msg.citedPages && msg.citedPages.length === 0 && msg.role === 'bot' && msg.id !== 1 && (
               <div className="cited-pages">
                 <span className="badge" style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.4)' }}>
                   No Document Sources Found
                 </span>
               </div>
            )}
          </div>
        ))}
        {isTyping && (
          <div className="message-bubble message-bot">
             <div className="typing-indicator">
              <span></span><span></span><span></span>
             </div>
          </div>
        )}
      </div>

      <form onSubmit={handleSend} className="chat-input-container">
        <input 
          type="text" 
          className="chat-input"
          placeholder="Ask a question about the document..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isTyping}
        />
        <button type="submit" className="send-button" disabled={!input.trim() || isTyping}>
          <Send size={20} />
        </button>
      </form>
    </div>
  );
};

export default Chat;
