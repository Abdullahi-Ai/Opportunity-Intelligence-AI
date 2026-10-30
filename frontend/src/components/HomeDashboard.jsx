import React from 'react';
import { 
  Sparkles, 
  Clock, 
  ExternalLink, 
  ArrowRight, 
  ShieldCheck, 
  Award, 
  Building2, 
  Briefcase, 
  GraduationCap, 
  Calendar,
  CheckCircle2
} from 'lucide-react';

export default function HomeDashboard({ 
  opportunities, 
  onSelectOpportunity, 
  onCheckEligibility, 
  onNavigateToExplore,
  onNavigateToAI 
}) {
  // Find next closing opportunity for the "Upcoming Deadlines" card
  const upcomingClosingOpp = opportunities.find(
    (o) => o.days_remaining !== null && o.days_remaining >= 0
  ) || opportunities[0];

  // Top 3 featured opportunities
  const featuredOpps = opportunities.slice(0, 3);

  const topInstitutions = [
    {
      name: 'University of Nairobi',
      location: 'Nairobi, Kenya',
      category: 'Public University',
      tag: 'HEF & Research Partner',
      gradient: 'from-blue-700 to-indigo-900',
    },
    {
      name: 'Safaricom HQ',
      location: 'Waiyaki Way, Nairobi',
      category: 'Telecommunications & Tech',
      tag: 'Youth Attachments',
      gradient: 'from-emerald-600 to-teal-900',
    },
    {
      name: 'KRA Times Tower',
      location: 'Haile Selassie Ave, Nairobi',
      category: 'Government Agency',
      tag: 'Graduate Trainee Scheme',
      gradient: 'from-rose-700 to-red-950',
    },
    {
      name: 'Equity Centre',
      location: 'Upper Hill, Nairobi',
      category: 'Financial & Philanthropy',
      tag: 'ELP Fellowships',
      gradient: 'from-amber-600 to-orange-900',
    },
  ];

  const officialPartners = [
    { name: 'Higher Education Financing (HEF)', url: 'https://www.hef.co.ke', category: 'Scholarships & Loans' },
    { name: 'Safaricom Career Portal', url: 'https://www.safaricom.co.ke/careers', category: 'Industrial Attachments' },
    { name: 'Public Service Commission (PSC PSIP)', url: 'https://www.publicservice.go.ke', category: 'Government Internships' },
    { name: 'Chevening UK Government', url: 'https://www.chevening.org/scholarship/kenya', category: 'International Masters' },
    { name: 'DAAD German Exchange Service', url: 'https://www.daad.or.ke', category: 'Postgraduate Fellowships' },
  ];

  return (
    <div className="space-y-8 animate-in fade-in duration-200">
      
      {/* Top Row: Hero Banner & Upcoming Deadline Card (Exact Layout of Image 1) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        
        {/* Left: Yellow/Gold Hero Banner (2 Columns) */}
        <div className="lg:col-span-2 rounded-3xl bg-gradient-to-r from-amber-400 via-amber-300 to-yellow-300 p-8 text-slate-900 shadow-sm relative overflow-hidden flex flex-col justify-between min-h-[220px]">
          <div className="max-w-md z-10 space-y-2">
            <span className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full bg-slate-900/10 text-slate-900 font-bold text-[11px] tracking-wide uppercase">
              <Sparkles className="w-3.5 h-3.5 text-amber-800" />
              <span>Agentic AI Grounded in Kenya</span>
            </span>
            <h2 className="text-2xl sm:text-3xl font-black tracking-tight text-slate-950">
              Explore new opportunities
            </h2>
            <p className="text-xs sm:text-sm font-medium text-slate-800 leading-relaxed">
              Opportunity search made smarter and simpler. Use our grounded AI assistant to discover attachments, scholarships, and graduate schemes with certified eligibility criteria.
            </p>
          </div>

          <div className="pt-4 z-10 flex items-center space-x-3">
            <button
              onClick={onNavigateToAI}
              className="px-6 py-2.5 bg-slate-950 hover:bg-slate-800 text-white font-bold text-xs rounded-full shadow-md transition-all hover:scale-[1.02]"
            >
              Try AI Advisor now
            </button>
            <button
              onClick={onNavigateToExplore}
              className="px-4 py-2.5 bg-white/60 hover:bg-white text-slate-900 font-bold text-xs rounded-full transition-colors"
            >
              Browse All Records
            </button>
          </div>

          {/* Decorative Illustration Silhouette */}
          <div className="absolute right-4 bottom-2 opacity-90 hidden sm:block pointer-events-none">
            <div className="w-36 h-36 rounded-full bg-yellow-200/50 flex items-center justify-center">
              <GraduationCap className="w-24 h-24 text-amber-900/30" />
            </div>
          </div>
        </div>

        {/* Right: Upcoming Deadlines Card (Dark Card from Image 1) */}
        <div className="rounded-3xl bg-slate-950 p-6 text-white shadow-sm flex flex-col justify-between relative overflow-hidden">
          <div>
            <div className="flex items-center justify-between text-xs text-slate-400 mb-3">
              <span className="font-semibold uppercase tracking-wider text-[10px] text-amber-400">
                Authoritative Countdown
              </span>
              <Clock className="w-4 h-4 text-amber-400" />
            </div>

            {upcomingClosingOpp ? (
              <div className="space-y-2">
                <span className="inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-400/20 text-amber-300 border border-amber-400/30">
                  {upcomingClosingOpp.deadline_status_label || 'Active Intake'}
                </span>
                <h3 className="font-bold text-base text-white line-clamp-2">
                  {upcomingClosingOpp.title}
                </h3>
                <p className="text-xs text-slate-400">
                  Provider: <span className="text-slate-200">{upcomingClosingOpp.provider}</span>
                </p>
                <div className="text-[11px] text-slate-400 flex items-center space-x-1.5 pt-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                  <span>Closing Date: {upcomingClosingOpp.application_deadline || 'Rolling Intake'}</span>
                </div>
              </div>
            ) : (
              <p className="text-xs text-slate-400">No urgent deadlines approaching.</p>
            )}
          </div>

          <div className="pt-4">
            <button
              onClick={() => upcomingClosingOpp && onSelectOpportunity(upcomingClosingOpp)}
              className="w-full py-2.5 px-4 bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs rounded-xl transition-colors shadow-sm text-center"
            >
              View Application Details
            </button>
          </div>
        </div>

      </div>

      {/* Middle Row: Featured Opportunities Grid (like "Courses" in Image 1) */}
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Featured Opportunities</h3>
            <p className="text-xs text-slate-500">Verified official programs with open applications for Kenyan students</p>
          </div>
          <button
            onClick={onNavigateToExplore}
            className="text-xs font-bold text-brand-600 hover:text-brand-800 flex items-center space-x-1"
          >
            <span>See all</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {featuredOpps.map((opp) => (
            <div
              key={opp.id}
              className="bg-white rounded-3xl p-5 border border-slate-200/80 hover:border-brand-300 hover:shadow-md transition-all duration-200 flex flex-col justify-between"
            >
              <div className="space-y-3">
                <div className="flex justify-between items-start gap-2">
                  <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-brand-50 text-brand-700">
                    {opp.category}
                  </span>
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                    opp.days_remaining !== null && opp.days_remaining <= 7
                      ? 'bg-rose-100 text-rose-700'
                      : 'bg-emerald-50 text-emerald-700'
                  }`}>
                    {opp.deadline_status_label || opp.status}
                  </span>
                </div>

                <div>
                  <h4 
                    onClick={() => onSelectOpportunity(opp)}
                    className="font-bold text-sm text-slate-900 hover:text-brand-600 cursor-pointer line-clamp-2"
                  >
                    {opp.title}
                  </h4>
                  <p className="text-xs text-slate-500 mt-1 flex items-center space-x-1">
                    <Building2 className="w-3 h-3 text-slate-400" />
                    <span className="truncate">{opp.provider}</span>
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-100 text-[11px] text-slate-600 space-y-1">
                  <p><span className="font-semibold text-slate-700">Target:</span> {opp.target_audience || 'University Students'}</p>
                  <p><span className="font-semibold text-slate-700">Degree:</span> {opp.degree_levels || 'Undergraduate'}</p>
                </div>
              </div>

              <div className="pt-4 mt-3 border-t border-slate-100 flex items-center justify-between gap-2">
                <button
                  onClick={() => onCheckEligibility(opp)}
                  className="flex-1 py-1.5 px-3 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-700 font-semibold text-xs border border-slate-200 transition-colors flex items-center justify-center space-x-1"
                >
                  <CheckCircle2 className="w-3.5 h-3.5 text-brand-600" />
                  <span>Check Criteria</span>
                </button>
                <button
                  onClick={() => onSelectOpportunity(opp)}
                  className="py-1.5 px-3 rounded-xl bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs transition-colors"
                >
                  Details
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Bottom Row: Top Institutions & Partner Portals (Exact Layout of Image 1) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left: Top Kenyan Institutions / Destinations (2 Columns) */}
        <div className="lg:col-span-2 space-y-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Top Opportunity Providers in Kenya</h3>
            <p className="text-xs text-slate-500">Certified organizations offering recurring attachments, scholarships, and trainee programs</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {topInstitutions.map((inst, idx) => (
              <div
                key={idx}
                className={`rounded-2xl p-5 bg-gradient-to-br ${inst.gradient} text-white shadow-sm flex flex-col justify-between min-h-[140px] relative overflow-hidden group hover:scale-[1.01] transition-transform`}
              >
                <div>
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-white/20 backdrop-blur-sm text-white">
                    {inst.tag}
                  </span>
                  <h4 className="font-bold text-base mt-2 text-white">{inst.name}</h4>
                  <p className="text-xs text-white/80">{inst.location}</p>
                </div>

                <div className="flex justify-between items-center pt-3 border-t border-white/10 text-[11px] text-white/90">
                  <span>{inst.category}</span>
                  <ArrowRight className="w-4 h-4 transform group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Verified Partner Portals (1 Column like Image 1 Partnerships) */}
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-bold text-slate-900">Official Direct Portals</h3>
            <p className="text-xs text-slate-500">Original government & agency submission sources</p>
          </div>

          <div className="bg-white rounded-3xl p-4 border border-slate-200/80 space-y-2">
            {officialPartners.map((p, idx) => (
              <a
                key={idx}
                href={p.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between p-3 rounded-2xl hover:bg-slate-50 border border-transparent hover:border-slate-200 transition-all group"
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="w-8 h-8 rounded-xl bg-brand-50 text-brand-700 flex items-center justify-center font-bold text-xs flex-shrink-0">
                    <ShieldCheck className="w-4 h-4 text-brand-600" />
                  </div>
                  <div className="truncate">
                    <p className="text-xs font-bold text-slate-800 truncate group-hover:text-brand-600 transition-colors">
                      {p.name}
                    </p>
                    <p className="text-[10px] text-slate-400 truncate">{p.category}</p>
                  </div>
                </div>

                <div className="w-7 h-7 rounded-full bg-slate-100 group-hover:bg-brand-600 group-hover:text-white flex items-center justify-center text-slate-400 transition-colors flex-shrink-0 ml-2">
                  <ExternalLink className="w-3.5 h-3.5" />
                </div>
              </a>
            ))}
          </div>
        </div>

      </div>

    </div>
  );
}
