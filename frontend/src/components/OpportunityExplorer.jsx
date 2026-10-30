import React from 'react';
import { 
  Filter, 
  X, 
  Building2, 
  ExternalLink, 
  Calendar, 
  CheckCircle2, 
  ShieldCheck, 
  BookmarkCheck,
  MapPin,
  Clock,
  Sparkles
} from 'lucide-react';

export default function OpportunityExplorer({
  opportunities,
  loading,
  error,
  searchQuery,
  setSearchQuery,
  selectedCategory,
  setSelectedCategory,
  isOpenOnly,
  setIsOpenOnly,
  onSelectOpportunity,
  onCheckEligibility,
  onSaveToTracker,
  trackedIds,
}) {
  const categories = [
    { label: 'All Opportunities', value: '' },
    { label: 'Scholarships & Bursaries', value: 'Scholarship' },
    { label: 'Internships & Attachments', value: 'Internship' },
    { label: 'Graduate Trainee Schemes', value: 'Graduate Trainee' },
    { label: 'Fellowships & Research', value: 'Fellowship' },
    { label: 'Competitions & Grants', value: 'Competition' },
  ];

  const degreeFilters = [
    'Undergraduate',
    'Diploma',
    'Masters',
    'Postgraduate'
  ];

  return (
    <div className="flex flex-col lg:flex-row gap-6 animate-in fade-in duration-200">
      
      {/* Left Filter Sidebar (Inspired directly by Reference 2 - CampusConnect) */}
      <aside className="w-full lg:w-64 bg-white rounded-3xl p-5 border border-slate-200/80 space-y-6 flex-shrink-0 h-fit">
        <div className="flex justify-between items-center pb-3 border-b border-slate-100">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-slate-700" />
            <h3 className="font-bold text-sm text-slate-900">Filters</h3>
          </div>
          {(selectedCategory || isOpenOnly || searchQuery) && (
            <button
              onClick={() => {
                setSelectedCategory('');
                setIsOpenOnly(false);
                setSearchQuery('');
              }}
              className="text-xs text-brand-600 hover:text-brand-800 font-semibold flex items-center space-x-1"
            >
              <span>Clear</span>
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Opportunity Type / Category */}
        <div className="space-y-2.5">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Opportunity Type</p>
          <div className="space-y-1.5">
            {categories.map((cat) => (
              <label
                key={cat.value}
                className="flex items-center space-x-2.5 text-xs text-slate-700 hover:text-slate-900 cursor-pointer py-0.5"
              >
                <input
                  type="radio"
                  name="category"
                  checked={selectedCategory === cat.value}
                  onChange={() => setSelectedCategory(cat.value)}
                  className="rounded-full text-brand-600 focus:ring-brand-500"
                />
                <span className={selectedCategory === cat.value ? 'font-bold text-brand-700' : 'font-medium'}>
                  {cat.label}
                </span>
              </label>
            ))}
          </div>
        </div>

        {/* Deadline Status Filter */}
        <div className="pt-2 border-t border-slate-100 space-y-2.5">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Availability</p>
          <label className="flex items-center space-x-2.5 text-xs text-slate-700 cursor-pointer">
            <input
              type="checkbox"
              checked={isOpenOnly}
              onChange={(e) => setIsOpenOnly(e.target.checked)}
              className="rounded text-brand-600 focus:ring-brand-500"
            />
            <span className="font-medium">Show Open & Active Deadlines Only</span>
          </label>
        </div>

        {/* Trust & Verification info box */}
        <div className="p-3 rounded-2xl bg-slate-50 border border-slate-200/80 text-[11px] text-slate-600 space-y-1">
          <div className="flex items-center space-x-1.5 font-bold text-slate-800">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>Anti-Scam Verified</span>
          </div>
          <p className="leading-snug text-slate-500">
            Every record is verified against official Kenya Gazette, university, or corporate notices.
          </p>
        </div>
      </aside>

      {/* Right Column: Opportunities Grid (Styled like Reference 2) */}
      <div className="flex-1 space-y-4">
        
        {/* Top Meta Bar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 bg-white px-5 py-3 rounded-2xl border border-slate-200/80 text-xs">
          <span className="font-bold text-slate-700">
            Showing <span className="text-brand-600">{opportunities.length}</span> verified opportunities
          </span>
          {searchQuery && (
            <span className="text-slate-500">
              Matching query: <strong className="text-slate-800">"{searchQuery}"</strong>
            </span>
          )}
        </div>

        {/* Grid of Cards */}
        {loading ? (
          <div className="py-24 text-center text-slate-500 bg-white rounded-3xl border border-slate-200/80">
            <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-sm font-medium">Fetching verified opportunities from knowledge base...</p>
          </div>
        ) : error ? (
          <div className="p-8 bg-rose-50 border border-rose-200 rounded-3xl text-center space-y-2">
            <h4 className="font-bold text-rose-900">API Connection Issue</h4>
            <p className="text-xs text-rose-700">{error}</p>
          </div>
        ) : opportunities.length === 0 ? (
          <div className="py-20 text-center bg-white rounded-3xl border border-slate-200 p-8 space-y-3">
            <h4 className="font-bold text-base text-slate-800">No opportunities match this filter</h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Try switching category filters or clearing your search query to explore other verified programs.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {opportunities.map((opp) => {
              const isSaved = trackedIds ? trackedIds.has(opp.id) : false;
              return (
                <div
                  key={opp.id}
                  className="bg-white rounded-3xl p-5 border border-slate-200/80 hover:border-brand-300 hover:shadow-md transition-all duration-200 flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    
                    {/* Header Row: Title and Category Badge (Image 2 style) */}
                    <div className="flex justify-between items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <h4 
                          onClick={() => onSelectOpportunity(opp)}
                          className="font-bold text-sm text-slate-900 hover:text-brand-600 cursor-pointer line-clamp-2"
                        >
                          {opp.title}
                        </h4>
                        <p className="text-xs font-medium text-slate-500 mt-0.5 flex items-center space-x-1">
                          <Building2 className="w-3 h-3 text-slate-400" />
                          <span>{opp.provider}</span>
                        </p>
                      </div>

                      <span className="px-2.5 py-1 rounded-xl text-[10px] font-bold bg-purple-50 text-purple-700 border border-purple-200/60 flex-shrink-0">
                        {opp.category}
                      </span>
                    </div>

                    {/* Attribute Pills: Location/Mode & Verified & Deadline */}
                    <div className="flex flex-wrap gap-1.5 text-[11px]">
                      <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-lg bg-emerald-50 text-emerald-800 font-semibold">
                        <ShieldCheck className="w-3 h-3 text-emerald-600" />
                        <span>Verified</span>
                      </span>

                      <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-lg font-semibold ${
                        opp.days_remaining !== null && opp.days_remaining <= 7
                          ? 'bg-rose-50 text-rose-700 border border-rose-200/70'
                          : 'bg-amber-50 text-amber-900 border border-amber-200/70'
                      }`}>
                        <Clock className="w-3 h-3 text-amber-700" />
                        <span>{opp.deadline_status_label || opp.status}</span>
                      </span>
                    </div>

                    {/* Target Audience & Degree Requirements */}
                    <div className="text-xs text-slate-600 space-y-1 pt-1">
                      <p className="line-clamp-2 text-slate-600 text-[11px] leading-relaxed">
                        Target: <span className="font-semibold text-slate-800">{opp.target_audience || 'Kenyan University Students'}</span>
                      </p>
                      <div className="flex flex-wrap gap-1 pt-1">
                        {opp.degree_levels?.split(',').map((deg, dIdx) => (
                          <span key={dIdx} className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px] font-medium">
                            {deg.trim()}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* Meta info: Deadline Date */}
                    <div className="text-[11px] text-slate-500 flex items-center space-x-1.5 pt-1">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      <span>Published Deadline: <strong>{opp.application_deadline || 'Rolling Admissions'}</strong></span>
                    </div>

                  </div>

                  {/* Bottom Action Row (Image 2 style) */}
                  <div className="pt-4 mt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                    <a
                      href={opp.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] font-semibold text-slate-500 hover:text-brand-700 flex items-center space-x-1"
                    >
                      <span>Official Source</span>
                      <ExternalLink className="w-3 h-3" />
                    </a>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => onCheckEligibility(opp)}
                        className="py-1.5 px-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold text-xs transition-colors"
                      >
                        Criteria
                      </button>
                      <button
                        onClick={() => onSelectOpportunity(opp)}
                        className="py-1.5 px-3.5 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs transition-colors shadow-sm"
                      >
                        View & Apply
                      </button>
                    </div>
                  </div>

                </div>
              );
            })}
          </div>
        )}

      </div>

    </div>
  );
}
