import React from 'react';
import { Search, ShieldCheck, Bell, User, Sparkles, Filter } from 'lucide-react';

export default function TopHeader({ 
  searchQuery, 
  setSearchQuery, 
  onSearch, 
  user, 
  onOpenAuth,
  onOpenProfile,
  onOpenAdmin
}) {
  return (
    <header className="h-16 bg-white border-b border-slate-200/80 px-6 flex items-center justify-between sticky top-0 z-20 shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
      
      {/* Search Input Bar (Inspired by Reference 1 & 2) */}
      <form onSubmit={onSearch} className="relative w-72 sm:w-96">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search opportunities, organizations, fields..."
          className="w-full bg-slate-50 hover:bg-slate-100/70 focus:bg-white text-xs font-medium text-slate-800 rounded-full pl-10 pr-4 py-2 border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all shadow-inner"
        />
      </form>

      {/* Right Controls */}
      <div className="flex items-center space-x-3">
        {/* Anti-Scam & Verification Status Pill */}
        <div className="hidden lg:flex items-center space-x-1.5 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/70 text-emerald-800 text-[11px] font-semibold">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
          <span>Verified Official Sources Only</span>
        </div>

        {/* User Pill / Login Trigger */}
        {user ? (
          <div className="flex items-center space-x-2">
            {user.role === 'admin' && (
              <span className="hidden sm:inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-300">
                Administrator
              </span>
            )}
            <button
              onClick={onOpenProfile}
              className="flex items-center space-x-2 p-1 pl-2 pr-3 rounded-full border border-slate-200 hover:border-brand-300 hover:bg-slate-50 transition-all"
            >
              <div className={`w-7 h-7 rounded-full font-bold flex items-center justify-center text-xs ${
                user.role === 'admin' ? 'bg-amber-100 text-amber-800' : 'bg-brand-100 text-brand-700'
              }`}>
                {user.full_name ? user.full_name.charAt(0).toUpperCase() : <User className="w-3.5 h-3.5" />}
              </div>
              <div className="text-left hidden md:block">
                <p className="text-xs font-bold text-slate-800 leading-none">{user.full_name.split(' ')[0]}</p>
                <p className="text-[10px] text-slate-400 capitalize">{user.role}</p>
              </div>
            </button>
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="px-4 py-1.5 rounded-full bg-slate-900 hover:bg-slate-800 text-white text-xs font-semibold shadow-sm transition-colors"
          >
            Sign In
          </button>
        )}
      </div>

    </header>
  );
}
