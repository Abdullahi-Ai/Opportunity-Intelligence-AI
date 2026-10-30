import React from 'react';
import { Calendar, ShieldCheck, ExternalLink, CheckCircle, Bookmark, Sparkles, ArrowRight } from 'lucide-react';

export default function OpportunityCard({ opportunity, onSelect, onCheckEligibility, onSave, isTracked }) {
  const getBadgeStyle = () => {
    if (opportunity.days_remaining === null || opportunity.days_remaining === undefined) {
      return 'bg-slate-100 text-slate-700 border-slate-200';
    }
    if (opportunity.days_remaining < 0) {
      return 'bg-rose-50 text-rose-700 border-rose-200';
    }
    if (opportunity.days_remaining <= 7) {
      return 'bg-amber-50 text-amber-700 border-amber-200 animate-pulse';
    }
    return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  };

  const getCategoryColor = (cat) => {
    switch (cat) {
      case 'Scholarship': return 'bg-purple-50 text-purple-700 border-purple-200';
      case 'Internship': return 'bg-blue-50 text-blue-700 border-blue-200';
      case 'Graduate Trainee': return 'bg-indigo-50 text-indigo-700 border-indigo-200';
      case 'Fellowship': return 'bg-teal-50 text-teal-700 border-teal-200';
      case 'Competition': return 'bg-orange-50 text-orange-700 border-orange-200';
      default: return 'bg-slate-50 text-slate-700 border-slate-200';
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm hover:shadow-md transition-all flex flex-col justify-between overflow-hidden group">
      
      {/* Top Banner */}
      <div className="p-5 pb-4">
        
        {/* Category & Status Bar */}
        <div className="flex items-center justify-between gap-2 mb-3">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className={`text-[11px] font-semibold px-2.5 py-1 rounded-full border ${getCategoryColor(opportunity.category)}`}>
              {opportunity.category}
            </span>
            {opportunity.is_verified && (
              <span className="flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                <span>Verified Official</span>
              </span>
            )}
          </div>

          {/* Countdown Badge */}
          <div className={`flex items-center space-x-1 text-xs font-semibold px-2.5 py-1 rounded-lg border ${getBadgeStyle()}`}>
            <Calendar className="w-3.5 h-3.5" />
            <span>{opportunity.deadline_status_label || opportunity.application_deadline}</span>
          </div>
        </div>

        {/* Title & Provider */}
        <h3 className="font-bold text-base text-slate-900 group-hover:text-brand-600 transition-colors line-clamp-2 leading-snug">
          {opportunity.title}
        </h3>
        <p className="text-xs font-medium text-slate-500 mt-1">
          {opportunity.provider}
        </p>

        {/* Target Audience / Summary */}
        {opportunity.target_audience && (
          <p className="text-xs text-slate-600 mt-2.5 line-clamp-2 leading-relaxed bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            {opportunity.target_audience}
          </p>
        )}

        {/* Degree & Field Tags */}
        <div className="flex flex-wrap gap-1.5 mt-3">
          {opportunity.degree_levels && (
            <span className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md">
              🎓 {opportunity.degree_levels}
            </span>
          )}
          {opportunity.fields_of_study && (
            <span className="text-[11px] px-2 py-0.5 bg-slate-100 text-slate-600 rounded-md line-clamp-1">
              📚 {opportunity.fields_of_study.slice(0, 32)}...
            </span>
          )}
        </div>

      </div>

      {/* Action Footer */}
      <div className="px-5 py-3.5 bg-slate-50/70 border-t border-slate-100 flex items-center justify-between gap-2">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onSelect(opportunity)}
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center space-x-1 py-1"
          >
            <span>Requirements</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
          <span className="text-slate-300">|</span>
          <button
            onClick={() => onCheckEligibility(opportunity)}
            className="text-xs font-semibold text-slate-700 hover:text-brand-600 flex items-center space-x-1 py-1"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-500" />
            <span>Check Fit</span>
          </button>
        </div>

        {/* Save / Track Button */}
        <button
          onClick={() => onSave(opportunity)}
          disabled={isTracked}
          className={`flex items-center space-x-1 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
            isTracked
              ? 'bg-emerald-100 text-emerald-800 cursor-default'
              : 'bg-white border border-slate-200 text-slate-700 hover:bg-brand-50 hover:text-brand-700 hover:border-brand-200 shadow-sm'
          }`}
        >
          {isTracked ? (
            <>
              <CheckCircle className="w-3.5 h-3.5 text-emerald-600" />
              <span>Tracked</span>
            </>
          ) : (
            <>
              <Bookmark className="w-3.5 h-3.5" />
              <span>Track</span>
            </>
          )}
        </button>
      </div>

    </div>
  );
}
