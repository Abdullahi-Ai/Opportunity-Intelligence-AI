import React from 'react';
import { Compass, BookmarkCheck, Bot, User, ShieldCheck } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab, student, onOpenProfile, onOpenAssistant }) {
  return (
    <header className="sticky top-0 z-30 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          
          {/* Logo & Brand */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('discover')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-700 to-brand-500 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
              <Compass className="w-6 h-6 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-lg text-slate-900 tracking-tight">Opportunity Intelligence</span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-brand-100 text-brand-800">KE</span>
              </div>
              <p className="text-[11px] text-slate-500 hidden sm:block">Verified Student Educational & Early-Career AI</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1 sm:space-x-2">
            <button
              onClick={() => setActiveTab('discover')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'discover'
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <Compass className="w-4 h-4" />
              <span>Discover</span>
            </button>

            <button
              onClick={() => setActiveTab('tracker')}
              className={`flex items-center space-x-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'tracker'
                  ? 'bg-brand-50 text-brand-700'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              }`}
            >
              <BookmarkCheck className="w-4 h-4" />
              <span>My Applications</span>
            </button>

            <button
              onClick={onOpenAssistant}
              className="flex items-center space-x-2 px-3.5 py-2 rounded-lg text-sm font-medium bg-gradient-to-r from-brand-600 to-brand-700 text-white shadow-sm hover:from-brand-700 hover:to-brand-800 transition-all hover:shadow"
            >
              <Bot className="w-4 h-4" />
              <span className="hidden sm:inline">AI Advisor</span>
            </button>
          </nav>

          {/* Student Profile Pill */}
          <div className="flex items-center pl-2">
            <button
              onClick={onOpenProfile}
              className="flex items-center space-x-2.5 p-1.5 sm:px-3 sm:py-1.5 rounded-full border border-slate-200 hover:border-brand-300 hover:bg-slate-50 transition-all"
            >
              <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 font-semibold flex items-center justify-center text-xs">
                {student?.full_name ? student.full_name.charAt(0).toUpperCase() : <User className="w-4 h-4" />}
              </div>
              <div className="text-left hidden md:block">
                <p className="text-xs font-semibold text-slate-800 leading-tight">
                  {student?.full_name || 'Set Up Profile'}
                </p>
                <p className="text-[10px] text-slate-500 leading-tight">
                  {student?.university || 'Kenyan University'}
                </p>
              </div>
            </button>
          </div>

        </div>
      </div>
    </header>
  );
}
