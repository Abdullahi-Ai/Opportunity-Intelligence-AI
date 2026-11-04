import React from 'react';
import { X, ShieldCheck, ExternalLink, Calendar, Bookmark, BookmarkCheck, CheckSquare, Sparkles, AlertCircle, Clock } from 'lucide-react';

export default function OpportunityModal({ opportunity, onClose, onCheckEligibility, onSave, isTracked }) {
  if (!opportunity) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-2xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        <div className="p-6 border-b border-slate-100 flex items-start justify-between bg-gradient-to-b from-brand-50/50 to-white">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-brand-100 text-brand-800">
                {opportunity.category}
              </span>
              {(opportunity.verification_status === 'VERIFIED' || (opportunity.is_verified && !opportunity.verification_status)) ? (
                <span className="flex items-center space-x-1 text-xs font-medium px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Verified Source</span>
                </span>
              ) : opportunity.verification_status === 'NEEDS_REVIEW' ? (
                <span className="flex items-center space-x-1 text-xs font-medium px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                  <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                  <span>Needs Review</span>
                </span>
              ) : opportunity.verification_status === 'PENDING_REVIEW' ? (
                <span className="flex items-center space-x-1 text-xs font-medium px-2 py-0.5 rounded-full bg-sky-50 text-sky-700 border border-sky-200">
                  <Clock className="w-3.5 h-3.5 text-sky-600" />
                  <span>Pending Review</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 text-xs font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
                  <span>Unverified</span>
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-900 leading-snug">{opportunity.title}</h2>
            <p className="text-sm font-medium text-slate-500 mt-1">{opportunity.provider}</p>
          </div>
          
          <button
            onClick={onClose}
            className="p-2 rounded-full hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5 text-sm text-slate-700">
          
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 p-4 bg-slate-50 rounded-2xl border border-slate-100 text-xs">
            <div>
              <span className="text-slate-400 block font-medium">Application Deadline</span>
              <span className="font-bold text-slate-800 flex items-center space-x-1 mt-0.5">
                <Calendar className="w-3.5 h-3.5 text-brand-600" />
                <span>{opportunity.application_deadline}</span>
              </span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Degree Level</span>
              <span className="font-semibold text-slate-800 mt-0.5 block">{opportunity.degree_levels || 'All Levels'}</span>
            </div>
            <div>
              <span className="text-slate-400 block font-medium">Verified On</span>
              <span className="font-semibold text-slate-800 mt-0.5 block">{opportunity.verification_date || 'Recently'}</span>
            </div>
          </div>

          {opportunity.target_audience && (
            <div>
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Target Audience</h4>
              <p className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs leading-relaxed text-slate-700">
                {opportunity.target_audience}
              </p>
            </div>
          )}

          {opportunity.fields_of_study && (
            <div>
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-400 mb-1.5">Eligible Fields of Study</h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                {opportunity.fields_of_study}
              </p>
            </div>
          )}

          {opportunity.source_notes && (
            <div className="p-3 bg-brand-50/60 rounded-xl border border-brand-100 text-xs text-brand-900 leading-relaxed">
              💡 <strong>Advisor Note:</strong> {opportunity.source_notes}
            </div>
          )}

          <div className="p-3 bg-amber-50 rounded-xl border border-amber-200 text-xs text-amber-900 leading-relaxed">
            🛡️ <strong>Safety & Anti-Scam Notice:</strong> This opportunity was sourced directly from the official portal. Never pay money or "medical exam clearance fees" for any attachment, internship, or scholarship application in Kenya.
          </div>

        </div>

        <div className="p-5 bg-slate-50 border-t border-slate-100 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => {
                onClose();
                onCheckEligibility(opportunity);
              }}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold bg-white border border-slate-200 text-slate-800 hover:bg-slate-100 transition-all shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span>Assess My Fit</span>
            </button>

            <button
              onClick={() => onSave(opportunity)}
              disabled={isTracked}
              className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-semibold transition-all shadow-sm ${
                isTracked
                  ? 'bg-emerald-100 text-emerald-800 cursor-default'
                  : 'bg-brand-600 hover:bg-brand-700 text-white'
              }`}
            >
              {isTracked ? (
                <>
                  <BookmarkCheck className="w-3.5 h-3.5" />
                  <span>Added to Tracker</span>
                </>
              ) : (
                <>
                  <Bookmark className="w-3.5 h-3.5" />
                  <span>Track Application</span>
                </>
              )}
            </button>
          </div>

          <a
            href={opportunity.official_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1 text-xs font-semibold text-brand-600 hover:text-brand-800 underline underline-offset-4"
          >
            <span>Visit Official Portal</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

      </div>
    </div>
  );
}
