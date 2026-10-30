import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import { 
  Bot, 
  Send, 
  Sparkles, 
  ExternalLink, 
  RefreshCw, 
  ShieldCheck, 
  User, 
  Trash2,
  CheckCircle2,
  FileCheck
} from 'lucide-react';
import { api } from '../api/client';

export default function AIAdvisorWorkspace({ student, user }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const starterCards = [
    {
      title: 'Safaricom Attachment Requirements',
      desc: 'Check eligibility criteria, required university endorsement letters, and application steps for 2026 intake.',
      query: 'What are the eligibility criteria and required documents for Safaricom industrial attachment?'
    },
    {
      title: 'HEF Government Funding & Bands',
      desc: 'Understand the Means Testing Instrument (MTI), student bands, and required statutory documents.',
      query: 'How do I apply for the HEF undergraduate scholarship and loan in Kenya?'
    },
    {
      title: 'KRA Graduate Trainee Program',
      desc: 'Verify degree requirements, age limits, and required academic certifications.',
      query: 'Can continuing students or fresh graduates apply for the KRA Graduate Trainee Program?'
    },
    {
      title: 'Chevening UK Master’s Scholarship',
      desc: 'Review the 2,800 hours work experience requirement, eligible courses, and timeline.',
      query: 'What are the work experience and eligibility requirements for Chevening scholarship in Kenya?'
    }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSendMessage = async (queryText = null) => {
    const textToSend = queryText || input;
    if (!textToSend.trim() || loading) return;

    const userMsg = { role: 'user', content: textToSend };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const studentId = student?.id || user?.id || 'guest_session';
      const data = await api.chat(textToSend, `workspace_session_${studentId}`, studentId);

      const assistantMsg = {
        role: 'assistant',
        content: data.response,
        citations: data.citations || [],
        tool_calls: data.tool_calls || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ I encountered an issue connecting to the AI knowledge base. Please verify the backend service is running and try again.',
          citations: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    if (messages.length > 0 && window.confirm('Clear conversation history?')) {
      setMessages([]);
    }
  };

  const displayName = user?.full_name || student?.full_name || 'Student';

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] bg-white rounded-3xl border border-slate-200/80 shadow-sm overflow-hidden animate-in fade-in duration-200">
      
      {/* Top Bar: Model Indicator & Controls (Image 3 Header) */}
      <div className="h-14 px-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50 flex-shrink-0">
        <div className="flex items-center space-x-2.5">
          <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-brand-600 to-indigo-600 flex items-center justify-center text-white shadow-sm">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="flex items-center space-x-2">
            <span className="font-bold text-xs text-slate-900">Opportunity AI 2.0</span>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/60">
              ChromaDB Grounded • Zero Hallucination Mode
            </span>
          </div>
        </div>

        {messages.length > 0 && (
          <button
            onClick={handleClearChat}
            className="flex items-center space-x-1 text-slate-400 hover:text-slate-600 text-xs px-2.5 py-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Chat</span>
          </button>
        )}
      </div>

      {/* Main Area: Empty State OR Message Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        
        {messages.length === 0 ? (
          /* Empty State Inspired Directly by Reference 3 (Spark.AI) */
          <div className="max-w-2xl mx-auto py-10 space-y-8 text-center animate-in fade-in zoom-in-95 duration-200">
            
            <div className="space-y-3">
              <div className="w-16 h-16 rounded-3xl bg-gradient-to-tr from-brand-500 via-indigo-500 to-amber-400 mx-auto flex items-center justify-center shadow-lg shadow-brand-500/20">
                <Bot className="w-8 h-8 text-white" />
              </div>
              <h2 className="text-3xl font-black text-slate-900 tracking-tight">
                Welcome, {displayName}!
              </h2>
              <p className="text-slate-500 text-sm max-w-md mx-auto">
                How can I assist your educational and career journey in Kenya today?
              </p>
            </div>

            {/* Central Prompt Input Box (Reference 3) */}
            <div className="bg-slate-50 border border-slate-200 rounded-3xl p-4 shadow-sm text-left space-y-3">
              <textarea
                rows={3}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSendMessage();
                  }
                }}
                placeholder="Ask about scholarships, attachment deadlines, eligibility requirements, or application checklists..."
                className="w-full bg-transparent text-xs sm:text-sm text-slate-800 placeholder-slate-400 focus:outline-none resize-none"
              />

              <div className="flex justify-between items-center pt-2 border-t border-slate-200/60">
                <div className="flex items-center space-x-2 text-[11px] text-slate-400">
                  <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-md bg-white border border-slate-200 font-medium">
                    <ShieldCheck className="w-3 h-3 text-emerald-600" />
                    <span>Deterministic Date Integrity</span>
                  </span>
                </div>

                <button
                  onClick={() => handleSendMessage()}
                  disabled={!input.trim() || loading}
                  className="px-5 py-2 bg-brand-600 hover:bg-brand-700 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-sm transition-all flex items-center space-x-1.5"
                >
                  <span>Send</span>
                  <Send className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Starter Suggestion Cards (Reference 3) */}
            <div className="space-y-3 text-left">
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Suggested Guidance Prompts:
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {starterCards.map((card, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendMessage(card.query)}
                    className="p-4 rounded-2xl bg-white border border-slate-200/80 hover:border-brand-300 hover:shadow-sm text-left transition-all group"
                  >
                    <p className="text-xs font-bold text-slate-800 group-hover:text-brand-600 transition-colors">
                      {card.title}
                    </p>
                    <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                      {card.desc}
                    </p>
                  </button>
                ))}
              </div>
            </div>

          </div>
        ) : (
          /* Active Chat Stream */
          <div className="max-w-3xl mx-auto space-y-4">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex items-start space-x-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-xl bg-brand-100 text-brand-700 flex items-center justify-center flex-shrink-0 mt-1">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div
                  className={`max-w-[85%] rounded-3xl p-5 leading-relaxed text-xs ${
                    msg.role === 'user'
                      ? 'bg-slate-900 text-white rounded-br-none shadow-sm'
                      : 'bg-slate-50 text-slate-800 rounded-bl-none border border-slate-200/80 shadow-sm'
                  }`}
                >
                  {msg.role === 'assistant' ? (
                    <div className="space-y-2 text-slate-800">
                      <ReactMarkdown
                        components={{
                          h3: ({ node, ...props }) => <h3 className="font-bold text-sm text-slate-900 mt-3 mb-1.5" {...props} />,
                          h4: ({ node, ...props }) => <h4 className="font-bold text-xs text-brand-900 mt-2 mb-1" {...props} />,
                          p: ({ node, ...props }) => <p className="text-xs leading-relaxed my-1.5" {...props} />,
                          ul: ({ node, ...props }) => <ul className="list-disc pl-4 space-y-1 my-2" {...props} />,
                          ol: ({ node, ...props }) => <ol className="list-decimal pl-4 space-y-1 my-2" {...props} />,
                          li: ({ node, ...props }) => <li className="text-xs leading-normal" {...props} />,
                          a: ({ node, ...props }) => (
                            <a
                              {...props}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-brand-600 hover:text-brand-800 underline font-bold inline-flex items-center space-x-0.5"
                            />
                          ),
                          blockquote: ({ node, ...props }) => (
                            <blockquote className="border-l-3 border-brand-500 pl-3 py-1 my-2 italic text-slate-600 bg-brand-50/60 rounded-r text-[11px]" {...props} />
                          ),
                          strong: ({ node, ...props }) => <strong className="font-bold text-slate-950" {...props} />,
                          code: ({ node, ...props }) => <code className="px-1.5 py-0.5 rounded bg-slate-200/70 text-[11px] font-mono text-slate-800" {...props} />
                        }}
                      >
                        {msg.content}
                      </ReactMarkdown>

                      {/* Official Sources Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-4 pt-3 border-t border-slate-200/80 text-[11px]">
                          <span className="font-bold text-slate-500 block mb-1.5">Official Verified Sources:</span>
                          <div className="flex flex-wrap gap-1.5">
                            {msg.citations.map((c, cIdx) => (
                              <a
                                key={cIdx}
                                href={c.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-white border border-slate-200 text-brand-700 hover:text-brand-900 font-medium shadow-2xs"
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
                  ) : (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  )}
                </div>

                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-xl bg-slate-200 text-slate-700 flex items-center justify-center flex-shrink-0 mt-1">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="flex items-center space-x-2 text-slate-500 text-xs py-2 pl-11">
                <RefreshCw className="w-4 h-4 animate-spin text-brand-600" />
                <span>Evaluating ChromaDB knowledge base & deterministic tools...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}

      </div>

      {/* Bottom Bar: Input when messages exist */}
      {messages.length > 0 && (
        <div className="p-4 border-t border-slate-100 bg-white flex-shrink-0">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="max-w-3xl mx-auto flex items-center space-x-2"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a follow-up question or request an application checklist..."
              className="flex-1 bg-slate-50 border border-slate-200 rounded-2xl px-4 py-3 text-xs focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="px-5 py-3 bg-brand-600 hover:bg-brand-700 text-white rounded-2xl text-xs font-bold shadow-sm transition-colors flex items-center space-x-1.5 disabled:opacity-50"
            >
              <span>Send</span>
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>
      )}

    </div>
  );
}
