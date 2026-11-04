import React, { useState, useEffect } from 'react';
import { 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Clock, 
  ExternalLink, 
  Bookmark, 
  BookmarkCheck, 
  GraduationCap, 
  Filter, 
  RefreshCw, 
  UserCheck, 
  ArrowRight,
  ShieldCheck,
  ChevronRight,
  Info
} from 'lucide-react';
import { api } from '../api/client';

export default function PersonalizedMatches({
  student,
  user,
  onSelectOpportunity,
  onCheckEligibility,
  onSaveToTracker,
  trackedIds = new Set(),
  savingIds = new Set(),
  onOpenProfile,
  onOpenAuth
}) {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const fetchMatches = async () => {
    if (!student && !user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const studentId = student?.id || null;
      const res = await api.getPersonalizedMatches(studentId);
      setMatches(res.matches || []);
    } catch (err) {
      console.error('Failed to load personalized matches:', err);
      setError('Could not retrieve personalized recommendations. Please verify backend connection.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMatches();
  }, [student, user]);

  if (!user && !student) {
    return (
      <div className="bg-white rounded-3xl p-12 border border-slate-200/80 text-center max-w-xl mx-auto space-y-5 animate-in fade-in duration-200">
        <div className="w-16 h-16 rounded-3xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center mx-auto shadow-sm">
          <Sparkles className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h3 className="text-xl font-black text-slate-900 tracking-tight">Personalized Matches</h3>
          <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
            Sign in with your university student account to unlock tailored scholarships, industrial attachments, and graduate schemes matched directly to your course, year, and degree level.
          </p>
        </div>
        <button
          onClick={onOpenAuth}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors"
        >
          Sign In or Register
        </button>
      </div>
    );
  }

  const filteredMatches = matches.filter((item) => {
    if (statusFilter === 'meets' && item.eligibility_status !== 'Meets requirements') return false;
    if (statusFilter === 'verification' && item.eligibility_status !== 'Needs verification') return false;
    if (categoryFilter !== 'all' && item.category !== categoryFilter) return false;
    return true;
  });

  const categories = Array.from(new Set(matches.map((m) => m.category))).filter(Boolean);

  const meetsCount = matches.filter((m) => m.eligibility_status === 'Meets requirements').length;
  const verificationCount = matches.filter((m) => m.eligibility_status === 'Needs verification').length;

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      
      <div className="bg-gradient-to-r from-brand-900 via-slate-900 to-indigo-950 rounded-3xl p-6 sm:p-8 text-white shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-2xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-amber-400/10 border border-amber-400/30 text-amber-300 text-[11px] font-bold uppercase tracking-wider">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Deterministic Academic Matching</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black tracking-tight">
            Personalized Opportunities for You
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Recommendations scored strictly against published eligibility criteria for{' '}
            <span className="font-semibold text-white">{student?.university || 'Kenyan University'}</span> students studying{' '}
            <span className="font-semibold text-white">{student?.field_of_study || 'your course'}</span>.
          </p>
          <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] text-slate-300">
            <span className="px-2.5 py-1 rounded-lg bg-white/10 font-medium">
              🎓 {student?.degree_level || 'Undergraduate'}
            </span>
            <span className="px-2.5 py-1 rounded-lg bg-white/10 font-medium">
              📚 Year {student?.year_of_study || 3} Continuing Student
            </span>
            {student?.preferred_categories && (
              <span className="px-2.5 py-1 rounded-lg bg-white/10 font-medium">
                🎯 {student?.preferred_categories}
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col sm:flex-row md:flex-col gap-2.5 flex-shrink-0">
          <button
            onClick={onOpenProfile}
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs border border-white/20 transition-colors flex items-center justify-center space-x-1.5"
          >
            <UserCheck className="w-3.5 h-3.5 text-amber-300" />
            <span>Update Profile Criteria</span>
          </button>
          <button
            onClick={fetchMatches}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs shadow-sm transition-colors flex items-center justify-center space-x-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Recommendations</span>
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider mr-1">Eligibility:</span>
          <button
            onClick={() => setStatusFilter('all')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all ${
              statusFilter === 'all'
                ? 'bg-slate-900 text-white shadow-2xs'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            All Matches ({matches.length})
          </button>
          <button
            onClick={() => setStatusFilter('meets')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-all ${
              statusFilter === 'meets'
                ? 'bg-emerald-600 text-white shadow-2xs'
                : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Meets Requirements ({meetsCount})</span>
          </button>
          <button
            onClick={() => setStatusFilter('verification')}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold flex items-center space-x-1.5 transition-all ${
              statusFilter === 'verification'
                ? 'bg-amber-600 text-white shadow-2xs'
                : 'bg-amber-50 text-amber-800 hover:bg-amber-100'
            }`}
          >
            <AlertCircle className="w-3.5 h-3.5" />
            <span>Needs Verification ({verificationCount})</span>
          </button>
        </div>

        {categories.length > 0 && (
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>{cat}</option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 py-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-white rounded-3xl p-6 border border-slate-200/80 shadow-2xs animate-pulse space-y-4">
              <div className="h-4 bg-slate-100 rounded w-1/3" />
              <div className="h-6 bg-slate-200 rounded w-3/4" />
              <div className="h-16 bg-slate-100 rounded" />
              <div className="h-8 bg-slate-100 rounded" />
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="bg-white rounded-3xl p-10 border border-rose-200 text-center space-y-4">
          <AlertCircle className="w-8 h-8 text-rose-500 mx-auto" />
          <h4 className="font-bold text-slate-900 text-sm">{error}</h4>
          <button
            onClick={fetchMatches}
            className="px-4 py-2 bg-brand-600 text-white text-xs font-bold rounded-xl"
          >
            Retry Loading
          </button>
        </div>
      ) : filteredMatches.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 border border-slate-200/80 text-center space-y-4">
          <GraduationCap className="w-10 h-10 text-slate-400 mx-auto" />
          <h4 className="font-extrabold text-slate-900 text-base">No Matching Opportunities for this Filter</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Try adjusting your eligibility filter, updating your course preferences in your student profile, or browsing the full opportunity explorer directory.
          </p>
          <button
            onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); }}
            className="px-4 py-2 bg-slate-900 text-white text-xs font-semibold rounded-xl"
          >
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
          {filteredMatches.map((item, index) => {
            const oppId = item.opportunity_id || item.id;
            const isSaved = (trackedIds?.has && oppId ? trackedIds.has(oppId) : false) || Boolean(item.is_saved);
            const isSaving = Boolean(savingIds?.has && oppId && savingIds.has(oppId));
            const isMeets = item.eligibility_status === 'Meets requirements';
            const isVerification = item.eligibility_status === 'Needs verification';

            return (
              <div
                key={oppId || `match-${index}`}
                className="bg-white rounded-3xl border border-slate-200/80 shadow-2xs hover:shadow-md hover:border-brand-200 transition-all flex flex-col justify-between overflow-hidden"
              >
                <div className="p-6 space-y-4">
                  
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[10px] font-extrabold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 tracking-wide">
                      {item.category}
                    </span>
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-black px-2 py-0.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-200/60">
                        {item.match_score}% Match
                      </span>
                      {(item.verification_status === 'VERIFIED' || (item.is_verified && !item.verification_status)) ? (
                        <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-emerald-700 px-2 py-0.5 rounded-full bg-emerald-50 border border-emerald-200">
                          <ShieldCheck className="w-3 h-3" />
                          <span>Verified</span>
                        </span>
                      ) : item.verification_status === 'NEEDS_REVIEW' ? (
                        <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-amber-700 px-2 py-0.5 rounded-full bg-amber-50 border border-amber-200">
                          <AlertCircle className="w-3 h-3" />
                          <span>Needs Review</span>
                        </span>
                      ) : item.verification_status === 'PENDING_REVIEW' ? (
                        <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-sky-700 px-2 py-0.5 rounded-full bg-sky-50 border border-sky-200">
                          <Clock className="w-3 h-3" />
                          <span>Pending Review</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 text-[10px] font-bold text-slate-600 px-2 py-0.5 rounded-full bg-slate-100 border border-slate-200">
                          <span>Unverified</span>
                        </span>
                      )}
                    </div>
                  </div>

                  <div>
                    <h3
                      onClick={() => onSelectOpportunity && onSelectOpportunity({ id: oppId, ...item })}
                      className="font-black text-slate-900 text-base leading-snug hover:text-brand-600 transition-colors cursor-pointer line-clamp-2"
                    >
                      {item.title}
                    </h3>
                    <p className="text-xs font-medium text-slate-500 mt-0.5">{item.provider}</p>
                  </div>

                  <div className="flex items-center space-x-2">
                    {isMeets ? (
                      <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-emerald-50 text-emerald-800 text-[11px] font-bold border border-emerald-200">
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Meets Requirements</span>
                      </span>
                    ) : isVerification ? (
                      <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-amber-50 text-amber-800 text-[11px] font-bold border border-amber-200">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Needs Verification</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-slate-100 text-slate-600 text-[11px] font-bold">
                        <span>Does Not Meet Criteria</span>
                      </span>
                    )}

                    {item.deadline_status_label && (
                      <span className="inline-flex items-center space-x-1 text-[11px] font-medium text-slate-600 px-2.5 py-1 rounded-xl bg-slate-50 border border-slate-200">
                        <Clock className="w-3 h-3 text-slate-400" />
                        <span>{item.deadline_status_label}</span>
                      </span>
                    )}
                  </div>

                  <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-3.5 text-xs text-slate-700 space-y-1.5">
                    <div className="flex items-center space-x-1.5 font-bold text-[11px] text-slate-900 uppercase tracking-wider">
                      <Info className="w-3.5 h-3.5 text-brand-600" />
                      <span>Why this matches you:</span>
                    </div>
                    <p className="text-xs text-slate-600 leading-relaxed font-normal">
                      {item.match_explanation}
                    </p>
                  </div>

                </div>

                <div className="px-6 py-4 bg-slate-50/50 border-t border-slate-100 flex items-center justify-between gap-3">
                  <button
                    onClick={() => onCheckEligibility && onCheckEligibility({ id: oppId, ...item })}
                    className="text-xs font-semibold text-brand-700 hover:text-brand-800 hover:underline flex items-center space-x-1"
                  >
                    <span>Inspect Criteria Breakdown</span>
                    <ChevronRight className="w-3.5 h-3.5" />
                  </button>

                  <div className="flex items-center space-x-2">
                    {item.official_url && (
                      <a
                        href={item.official_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 rounded-xl bg-white border border-slate-200 text-slate-600 hover:text-slate-900 transition-colors"
                        title="View Official Portal"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                    <button
                      disabled={isSaved || isSaving}
                      onClick={() => !isSaved && !isSaving && onSaveToTracker && onSaveToTracker({ id: oppId, ...item })}
                      className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center space-x-1.5 shadow-2xs ${
                        isSaved
                          ? 'bg-emerald-50 text-emerald-800 border border-emerald-200 cursor-default'
                          : isSaving
                          ? 'bg-brand-400 text-white cursor-wait opacity-85'
                          : 'bg-brand-600 hover:bg-brand-700 text-white cursor-pointer'
                      }`}
                    >
                      {isSaved ? (
                        <>
                          <BookmarkCheck className="w-3.5 h-3.5 text-emerald-600" />
                          <span>Saved in Planner</span>
                        </>
                      ) : isSaving ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>Saving...</span>
                        </>
                      ) : (
                        <>
                          <Bookmark className="w-3.5 h-3.5" />
                          <span>Save to Planner</span>
                        </>
                      )}
                    </button>
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
