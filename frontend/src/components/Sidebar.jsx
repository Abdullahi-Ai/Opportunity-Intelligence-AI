import React from 'react';
import { 
  Home, 
  Compass, 
  Bot, 
  BookmarkCheck, 
  CheckCircle2, 
  ShieldCheck, 
  User, 
  LogIn, 
  LogOut, 
  Sparkles,
  HelpCircle,
  FileText
} from 'lucide-react';

export default function Sidebar({ 
  activeTab, 
  setActiveTab, 
  user, 
  onOpenAuth, 
  onOpenProfile, 
  onOpenAdmin,
  onOpenAssistantDrawer 
}) {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home },
    { id: 'explore', label: 'Discover Opportunities', icon: Compass },
    { id: 'matches', label: 'Personalized Matches', icon: Sparkles, badge: 'Smart' },
    { id: 'planner', label: 'Application Planner', icon: BookmarkCheck },
    { id: 'ai-workspace', label: 'AI Advisor Workspace', icon: Bot, badge: 'RAG' },
    { id: 'eligibility', label: 'Eligibility Checker', icon: CheckCircle2 },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200/80 flex flex-col justify-between flex-shrink-0 h-screen sticky top-0 z-30 shadow-[1px_0_10px_rgba(0,0,0,0.02)]">
      
      <div>
        <div className="p-5 border-b border-slate-100 flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('dashboard')}>
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-brand-700 via-brand-600 to-brand-500 flex items-center justify-center text-white shadow-md shadow-brand-500/25">
            <Compass className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <span className="font-extrabold text-base text-slate-900 tracking-tight">Opportunity AI</span>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-md bg-brand-100 text-brand-800 uppercase tracking-wider">KE</span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">University Intelligence</p>
          </div>
        </div>

        <div className="px-3 py-4 space-y-1">
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">Main Menu</p>
          
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all duration-150 ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center space-x-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-amber-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </div>
                {item.badge && (
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-bold ${
                    isActive ? 'bg-amber-400 text-slate-900' : 'bg-brand-50 text-brand-700'
                  }`}>
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}

          {user?.role === 'admin' && (
            <div className="pt-2">
              <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-amber-800/80 mb-1.5">Management</p>
              <button
                onClick={onOpenAdmin}
                className="w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold text-amber-900 bg-amber-50/80 hover:bg-amber-100/80 border border-amber-200 transition-colors"
              >
                <ShieldCheck className="w-4 h-4 text-amber-600" />
                <span>Admin Portal</span>
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="p-3 border-t border-slate-100 space-y-3">
        
        <div className="p-3 rounded-2xl bg-gradient-to-br from-brand-50 via-slate-50 to-amber-50/40 border border-brand-100/60 text-xs">
          <div className="flex items-center space-x-2 mb-1.5">
            <div className="w-6 h-6 rounded-lg bg-brand-600 text-white flex items-center justify-center">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <div>
              <p className="font-bold text-slate-800 text-[11px]">Need Advice?</p>
              <p className="text-[10px] text-slate-500">Ask Opportunity AI</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-600 leading-snug mb-2">
            Instant eligibility checks, deadline countdowns & preparation checklists.
          </p>
          <button
            onClick={() => setActiveTab('ai-workspace')}
            className="w-full py-1.5 px-2.5 bg-slate-900 hover:bg-slate-800 text-white font-semibold text-[11px] rounded-lg transition-colors text-center"
          >
            Open AI Workspace
          </button>
        </div>

        {user ? (
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-200/80">
            <button
              onClick={onOpenProfile}
              className="flex items-center space-x-2.5 text-left flex-1 min-w-0"
            >
              <div className={`w-8 h-8 rounded-full font-bold flex items-center justify-center text-xs flex-shrink-0 ${
                user.role === 'admin' ? 'bg-amber-100 text-amber-800' : 'bg-brand-100 text-brand-700'
              }`}>
                {user.full_name ? user.full_name.charAt(0).toUpperCase() : <User className="w-4 h-4" />}
              </div>
              <div className="truncate">
                <p className="text-xs font-bold text-slate-800 truncate">{user.full_name}</p>
                <p className="text-[10px] text-slate-500 truncate capitalize">{user.role}</p>
              </div>
            </button>
            <button
              onClick={onOpenAuth}
              className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/60"
              title="Account settings / Sign Out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="w-full flex items-center justify-center space-x-2 py-2 px-3 rounded-xl bg-brand-50 hover:bg-brand-100 border border-brand-200 text-brand-700 font-semibold text-xs transition-colors"
          >
            <LogIn className="w-3.5 h-3.5" />
            <span>Sign In / Register</span>
          </button>
        )}

      </div>
    </aside>
  );
}
