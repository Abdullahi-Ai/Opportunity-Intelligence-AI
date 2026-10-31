import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { X, Bot, Send, Sparkles, ExternalLink, RefreshCw, ShieldCheck, User } from 'lucide-react';
import { api } from '../api/client';

export default function AIAssistantDrawer({ isOpen, onClose, student }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Hello ${student?.full_name || 'there'}! 👋 I am your **Opportunity Intelligence AI Advisor**.\n\nI can help you:\n- **Find verified attachments and internships** in Kenya.\n- **Check your eligibility** for scholarships like HEF, Mastercard Foundation, or Chevening.\n- **Generate application checklists** for required statutory documents.\n\nWhat opportunity can I research for you today?`,
      citations: [],
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const starterPrompts = [
    'What are the requirements for Safaricom attachment?',
    'What documents do I need for HEF scholarship in Kenya?',
    'Can continuing students apply for KRA internship?',
    'What are the work experience requirements for Chevening?',
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const data = await api.chat(text, 'student_session_01', student?.id);
      const botMsg = {
        role: 'assistant',
        content: data.response,
        citations: data.citations || [],
        tool_calls: data.tool_calls || [],
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Sorry, I encountered an issue connecting to the knowledge base. Please try again.',
          citations: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full sm:w-[480px] bg-white shadow-2xl border-l border-slate-200 flex flex-col animate-in slide-in-from-right duration-200">
      
      <div className="p-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-brand-700 to-brand-600 text-white">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-lg bg-white/20 backdrop-blur-sm flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h3 className="font-bold text-sm tracking-tight">Opportunity AI Assistant</h3>
            <p className="text-[11px] text-brand-100">Grounded in Verified Official Sources</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-white/10 text-white/80 hover:text-white transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex items-start space-x-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            {msg.role === 'assistant' && (
              <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center flex-shrink-0 mt-1">
                <Bot className="w-3.5 h-3.5" />
              </div>
            )}

            <div
              className={`max-w-[85%] rounded-2xl p-3.5 leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-brand-600 text-white rounded-br-none shadow-sm'
                  : 'bg-slate-100 text-slate-800 rounded-bl-none border border-slate-200/60 shadow-sm'
              }`}
            >
              {msg.role === 'assistant' ? (
                <div className="text-slate-800 space-y-1.5 leading-relaxed">
                  <ReactMarkdown
                    components={{
                      h3: ({ node, ...props }) => <h3 className="font-bold text-sm text-slate-900 mt-2 mb-1" {...props} />,
                      h4: ({ node, ...props }) => <h4 className="font-semibold text-xs text-brand-900 mt-2 mb-0.5" {...props} />,
                      p: ({ node, ...props }) => <p className="text-xs leading-relaxed my-1" {...props} />,
                      ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 my-1" {...props} />,
                      ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 my-1" {...props} />,
                      li: ({ node, ...props }) => <li className="text-xs leading-normal" {...props} />,
                      a: ({ node, ...props }) => (
                        <a
                          {...props}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand-600 hover:text-brand-800 underline font-semibold inline-flex items-center space-x-0.5"
                        />
                      ),
                      blockquote: ({ node, ...props }) => (
                        <blockquote className="border-l-2 border-brand-500 pl-2.5 py-1 my-1.5 italic text-slate-600 bg-brand-50/60 rounded-r text-[11px]" {...props} />
                      ),
                      strong: ({ node, ...props }) => <strong className="font-bold text-slate-900" {...props} />,
                      code: ({ node, ...props }) => <code className="px-1 py-0.5 rounded bg-slate-200/80 text-[11px] font-mono text-slate-800" {...props} />
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="whitespace-pre-wrap text-xs">{msg.content}</div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3 pt-2.5 border-t border-slate-200/80 text-[11px]">
                  <span className="font-semibold text-slate-500 block mb-1">Official Sources:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {msg.citations.map((c, cIdx) => (
                      <a
                        key={cIdx}
                        href={c.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-white border border-slate-200 text-brand-700 hover:text-brand-900 font-medium"
                      >
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        <span>{c.title}</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {msg.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center flex-shrink-0 mt-1">
                <User className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex items-center space-x-2 text-slate-500 text-xs py-2">
            <RefreshCw className="w-4 h-4 animate-spin text-brand-600" />
            <span>Consulting ChromaDB knowledge base & evaluating tools...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {messages.length <= 2 && (
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
            Suggested Queries:
          </span>
          <div className="flex flex-wrap gap-1.5">
            {starterPrompts.map((prompt, i) => (
              <button
                key={i}
                onClick={() => handleSend(prompt)}
                className="text-[11px] px-2.5 py-1 bg-white border border-slate-200 rounded-lg text-slate-700 hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200 text-left transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="p-3 border-t border-slate-200 bg-white">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center space-x-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about scholarships, attachment deadlines..."
            className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-3.5 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500 focus:bg-white"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="p-2.5 rounded-xl bg-brand-600 hover:bg-brand-700 disabled:bg-slate-200 text-white transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        <p className="text-[10px] text-slate-400 text-center mt-1.5">
          Answers grounded strictly in verified Kenyan educational databases.
        </p>
      </div>

    </div>
  );
}
