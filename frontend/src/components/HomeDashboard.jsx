import React, { useState, useEffect } from 'react';
import { 
  Compass, 
  Sparkles, 
  Bot, 
  BookmarkCheck, 
  Calendar, 
  CheckCircle2, 
  ArrowRight, 
  ShieldCheck, 
  Clock, 
  Award, 
  ChevronRight,
  TrendingUp,
  FileCheck2,
  AlertCircle
} from 'lucide-react';
import { api, getToken } from '../api/client';

export default function HomeDashboard({ 
  opportunities = [], 
  onSelectOpportunity, 
  onCheckEligibility, 
  onNavigateToExplore, 
  onNavigateToAI,
  onNavigateToMatches,
  onNavigateToPlanner
}) {
  const [stats, setStats] = useState(null);
  const [matches, setMatches] = useState([]);
  const [loadingMatches, setLoadingMatches] = useState(false);
  const hasToken = Boolean(getToken());

  useEffect(() => {
    if (!hasToken) return;

    const fetchDashboardData = async () => {
      try {
        const statsData = await api.getTrackerStats();
        setStats(statsData);
      } catch (err) {
        setStats(null);
      }

      setLoadingMatches(true);
      try {
        const matchData = await api.getPersonalizedMatches();
        setMatches(matchData.slice(0, 3));
      } catch (err) {
        setMatches([]);
      } finally {
        setLoadingMatches(false);
      }
    };

    fetchDashboardData();
  }, [hasToken]);

  const verifiedOpps = opportunities.filter((o) => o.is_verified);
  const activeOpps = opportunities.filter((o) => o.is_open);
  const totalVerifiedProviders = new Set(opportunities.map((o) => o.provider)).size;

  return (
    <div className="space-y-8 animate-fade-in">
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-950 via-slate-900 to-brand-950 text-white p-8 md:p-10 shadow-xl border border-slate-800">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-brand-500/20 border border-brand-400/30 text-brand-300 text-xs font-semibold uppercase tracking-wider mb-4">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Agentic Intelligence & Deterministic Verification</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-3">
            Opportunities built for your academic journey.
          </h1>
          <p className="text-sm text-slate-300 leading-relaxed mb-6 font-normal">
            Kenya's verified university intelligence hub. Zero halluncinations, strict source attribution, and deterministic eligibility evaluations for attachments, scholarships, and graduate programs.
          </p>

          <div className="flex flex-wrap gap-3">
            <button
              onClick={onNavigateToExplore}
              className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-brand-600 hover:bg-brand-500 text-white text-xs font-bold transition-all shadow-md shadow-brand-600/30 active:scale-95"
            >
              <Compass className="w-4 h-4" />
              <span>Explore All Opportunities</span>
            </button>
            {onNavigateToMatches && (
              <button
                onClick={onNavigateToMatches}
                className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20 active:scale-95"
              >
                <Sparkles className="w-4 h-4 text-slate-950" />
                <span>Personalized Matches</span>
              </button>
            )}
            <button
              onClick={onNavigateToAI}
              className="inline-flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-slate-800/80 hover:bg-slate-700/80 text-slate-200 border border-slate-700 text-xs font-bold transition-all active:scale-95"
            >
              <Bot className="w-4 h-4 text-amber-400" />
              <span>Ask AI Advisor</span>
            </button>
          </div>
        </div>

        <div className="absolute -right-10 -bottom-10 w-96 h-96 bg-brand-600/10 rounded-full blur-3xl pointer-events-none" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
            <Compass className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-slate-900">{opportunities.length}</p>
            <p className="text-xs font-semibold text-slate-500">Curated Listings</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-slate-900">{verifiedOpps.length}</p>
            <p className="text-xs font-semibold text-slate-500">Strictly Verified</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
            <Award className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-slate-900">{totalVerifiedProviders}</p>
            <p className="text-xs font-semibold text-slate-500">Official Providers</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-slate-200/80 shadow-sm flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <p className="text-2xl font-black text-slate-900">{activeOpps.length}</p>
            <p className="text-xs font-semibold text-slate-500">Applications Open</p>
          </div>
        </div>
      </div>

      {hasToken && stats && (
        <div className="bg-white rounded-3xl border border-slate-200/80 p-6 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-2">
              <TrendingUp className="w-5 h-5 text-brand-600" />
              <h2 className="text-base font-bold text-slate-900">Your Application Pipeline</h2>
            </div>
            {onNavigateToPlanner && (
              <button
                onClick={onNavigateToPlanner}
                className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center space-x-1"
              >
                <span>View Full Planner</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="p-3.5 rounded-2xl bg-slate-50 border border-slate-100">
              <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">Total Tracked</span>
              <p className="text-xl font-extrabold text-slate-900 mt-1">{stats.total_tracked}</p>
            </div>
            <div className="p-3.5 rounded-2xl bg-amber-50 border border-amber-100">
              <span className="text-[11px] font-semibold text-amber-700 uppercase tracking-wider">In Progress</span>
              <p className="text-xl font-extrabold text-amber-900 mt-1">
                {(stats.by_stage?.Drafting || 0) + (stats.by_stage?.Saved || 0)}
              </p>
            </div>
            <div className="p-3.5 rounded-2xl bg-blue-50 border border-blue-100">
              <span className="text-[11px] font-semibold text-blue-700 uppercase tracking-wider">Submitted / Review</span>
              <p className="text-xl font-extrabold text-blue-900 mt-1">
                {(stats.by_stage?.Submitted || 0) + (stats.by_stage?.Interview || 0)}
              </p>
            </div>
            <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-100">
              <span className="text-[11px] font-semibold text-emerald-700 uppercase tracking-wider">Tasks Done</span>
              <p className="text-xl font-extrabold text-emerald-900 mt-1">
                {stats.completed_tasks} / {stats.total_tasks}
              </p>
            </div>
          </div>
        </div>
      )}

      {matches.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
                <Sparkles className="w-5 h-5 text-amber-500" />
                <span>Top Personalized Recommendations</span>
              </h2>
              <p className="text-xs text-slate-500">Evaluated deterministically from your degree, field, and year</p>
            </div>
            {onNavigateToMatches && (
              <button
                onClick={onNavigateToMatches}
                className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center space-x-1"
              >
                <span>See all matches</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {matches.map((item) => (
              <div
                key={item.opportunity.id}
                className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-brand-50 text-brand-700">
                      {item.opportunity.category}
                    </span>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md ${
                      item.eligibility_status === 'Meets requirements'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}>
                      {item.match_score}% Match
                    </span>
                  </div>
                  <h3 className="font-bold text-sm text-slate-900 line-clamp-1">{item.opportunity.title}</h3>
                  <p className="text-xs font-medium text-slate-500 mt-0.5">{item.opportunity.provider}</p>
                  <p className="text-[11px] text-slate-600 mt-3 line-clamp-2 bg-slate-50 p-2 rounded-lg border border-slate-100">
                    {item.match_explanation}
                  </p>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                  <button
                    onClick={() => onSelectOpportunity(item.opportunity)}
                    className="text-xs font-bold text-brand-600 hover:text-brand-800"
                  >
                    View Details
                  </button>
                  <button
                    onClick={() => onCheckEligibility(item.opportunity)}
                    className="text-xs font-semibold text-slate-600 hover:text-slate-900"
                  >
                    Verify Criteria
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Featured Kenya Opportunities</h2>
            <p className="text-xs text-slate-500">Official postings verified for Kenyan university students</p>
          </div>
          <button
            onClick={onNavigateToExplore}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center space-x-1"
          >
            <span>View directory</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {opportunities.slice(0, 6).map((opp) => (
            <div
              key={opp.id}
              className="bg-white rounded-2xl border border-slate-200/80 p-5 shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md bg-slate-100 text-slate-700">
                    {opp.category}
                  </span>
                  {opp.is_verified && (
                    <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                      <ShieldCheck className="w-3 h-3" />
                      <span>Verified</span>
                    </span>
                  )}
                </div>

                <h3 className="font-bold text-sm text-slate-900 line-clamp-2 leading-snug">{opp.title}</h3>
                <p className="text-xs font-medium text-slate-500 mt-1">{opp.provider}</p>

                <p className="text-xs text-slate-600 mt-3 line-clamp-3 leading-relaxed">
                  {opp.description}
                </p>
              </div>

              <div className="mt-5 pt-4 border-t border-slate-100 space-y-3">
                <div className="flex items-center justify-between text-[11px] text-slate-500">
                  <span className="inline-flex items-center space-x-1">
                    <Calendar className="w-3.5 h-3.5" />
                    <span>{opp.deadline ? `Deadline: ${new Date(opp.deadline).toLocaleDateString()}` : 'Rolling Deadline'}</span>
                  </span>
                  <span className={`font-semibold ${opp.is_open ? 'text-emerald-600' : 'text-slate-400'}`}>
                    {opp.is_open ? 'Open' : 'Closed'}
                  </span>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => onSelectOpportunity(opp)}
                    className="flex-1 py-1.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs transition-colors"
                  >
                    Details
                  </button>
                  <button
                    onClick={() => onCheckEligibility(opp)}
                    className="flex-1 py-1.5 px-3 rounded-xl bg-brand-50 hover:bg-brand-100 text-brand-700 font-semibold text-xs transition-colors"
                  >
                    Check Fit
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}