import React, { useState, useRef, useEffect } from 'react';
import { Send, FileText, ChevronDown, ChevronUp, Brain, Search, BookOpen } from 'lucide-react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

/* Map tool names to icons and labels */
const TOOL_META = {
  get_document_metadata:  { icon: FileText,  label: 'Reading Document Info',   color: '#60a5fa' },
  get_document_structure: { icon: Brain,      label: 'Analyzing Structure',     color: '#a78bfa' },
  get_page_content:       { icon: BookOpen,   label: 'Fetching Page Content',   color: '#34d399' },
};

/* Collapsible panel showing the agent's tool call trace */
const ToolTrace = ({ toolCalls }) => {
  const [expanded, setExpanded] = useState(false);
  if (!toolCalls || toolCalls.length === 0) return null;

  return (
    <div className="tool-trace">
      <button className="tool-trace-toggle" onClick={() => setExpanded(!expanded)}>
        <Search size={14} />
        <span>Agent Reasoning ({toolCalls.length} tool calls)</span>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>
      {expanded && (
        <div className="tool-trace-list">
          {toolCalls.map((tc, i) => {
            const meta = TOOL_META[tc.tool_name] || { icon: Search, label: tc.tool_name, color: '#94a3b8' };
            const Icon = meta.icon;
            const argsStr = tc.arguments && Object.keys(tc.arguments).length > 0
              ? JSON.stringify(tc.arguments)
              : '';
            return (
              <div key={i} className="tool-trace-item">
                <div className="tool-trace-header">
                  <Icon size={14} style={{ color: meta.color, flexShrink: 0 }} />
                  <span className="tool-trace-label" style={{ color: meta.color }}>{meta.label}</span>
                  {argsStr && <code className="tool-trace-args">{argsStr}</code>}
                </div>
                <div className="tool-trace-preview">{tc.result_preview}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};


const Chat = ({ documentId }) => {
  const [messages, setMessages] = useState([
    { id: 1, role: 'bot', text: 'Document analyzed and indexed. I can now reason over its structure. What would you like to know?' }
  ]);
  const [conversationHistory, setConversationHistory] = useState([]);
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

    const userText = input.trim();
    const userMessage = { id: Date.now(), role: 'user', text: userText };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      const res = await axios.post(`${API_URL}/chat`, {
        document_id: documentId,
        query: userText,
        conversation_history: conversationHistory,
      });

      const botMessage = {
        id: Date.now() + 1,
        role: 'bot',
        text: res.data.answer,
        citedPages: res.data.cited_pages,
        toolCalls: res.data.tool_calls,
      };

      setMessages(prev => [...prev, botMessage]);

      /* Update conversation history for multi-turn memory */
      setConversationHistory(prev => [
        ...prev,
        { role: 'user', content: userText },
        { role: 'assistant', content: res.data.answer },
      ]);

    } catch (err) {
      console.error(err);
      const errorMessage = {
        id: Date.now() + 1,
        role: 'bot',
        text: 'Sorry, I encountered an error communicating with the agent.',
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

            {/* Tool call trace (agentic transparency) */}
            {msg.toolCalls && <ToolTrace toolCalls={msg.toolCalls} />}

            {/* Cited pages badges */}
            {msg.citedPages && msg.citedPages.length > 0 && (
              <div className="cited-pages">
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sources:</span>
                {msg.citedPages.map(page => (
                  <span key={page} className="badge">
                    <FileText size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: 'text-bottom' }} />
                    Page {page}
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
