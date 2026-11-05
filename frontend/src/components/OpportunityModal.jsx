import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, ExternalLink, Calendar, Bookmark, BookmarkCheck, Sparkles, AlertCircle, Clock, CheckCircle2, XCircle, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../api/client';

export default function OpportunityModal({ opportunity, onClose, onCheckEligibility, onSave, isTracked }) {
  const [criteria, setCriteria] = useState([]);
  const [loadingCriteria, setLoadingCriteria] = useState(false);
  const [criteriaError, setCriteriaError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    if (opportunity && opportunity.id) {
      setLoadingCriteria(true);
      setCriteriaError(null);
      api.getOpportunityCriteria(opportunity.id)
        .then(res => {
          if (isMounted) {
            setCriteria(Array.isArray(res) ? res : []);
            setLoadingCriteria(false);
          }
        })
        .catch(err => {
          if (isMounted) {
            // Non-blocking: fail quietly if criteria are not loaded
            setCriteria([]);
            setLoadingCriteria(false);
          }
        });
    }
    return () => { isMounted = false; };
  }, [opportunity?.id]);

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

          {/* Structured Eligibility Criteria Section */}
          <div className="border border-slate-200 rounded-2xl p-4 bg-slate-50/50">
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-bold text-xs uppercase tracking-wider text-slate-600 flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4 text-brand-600" />
                <span>Structured Eligibility Criteria</span>
              </h4>
              <span className="text-xs text-slate-400">
                {loadingCriteria ? 'Loading...' : `${criteria.length} recorded`}
              </span>
            </div>

            {loadingCriteria ? (
              <div className="text-center py-4 text-xs text-slate-400 animate-pulse">
                Fetching structured eligibility requirements...
              </div>
            ) : criteria.length === 0 ? (
              <p className="text-xs text-slate-500 italic p-2 bg-white rounded-lg border border-slate-100">
                No structured criteria extracted yet for this opportunity. Eligibility is assessed against overall program guidelines.
              </p>
            ) : (
              <div className="space-y-2">
                {criteria.map((c) => (
                  <div key={c.id} className="p-3 bg-white rounded-xl border border-slate-200 shadow-sm text-xs space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center space-x-1.5 flex-wrap">
                        <span className="font-bold text-slate-800 uppercase text-[10px] tracking-wide px-2 py-0.5 rounded bg-slate-100 border border-slate-200">
                          {c.criterion_type.replace('_', ' ')}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                          c.is_mandatory 
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                        }`}>
                          {c.is_mandatory ? 'Mandatory' : 'Desirable'}
                        </span>
                        {c.target_scale && (
                          <span className="text-[10px] font-medium text-slate-500 bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200">
                            Scale: {c.target_scale}
                          </span>
                        )}
                      </div>
                      <span className={`flex items-center space-x-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        c.verification_status === 'VERIFIED'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : c.verification_status === 'NEEDS_REVIEW'
                          ? 'bg-amber-50 text-amber-700 border border-amber-200'
                          : c.verification_status === 'REJECTED'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-sky-50 text-sky-700 border border-sky-200'
                      }`}>
                        {c.verification_status === 'VERIFIED' && <ShieldCheck className="w-3 h-3 text-emerald-600" />}
                        {c.verification_status === 'NEEDS_REVIEW' && <AlertCircle className="w-3 h-3 text-amber-600" />}
                        {c.verification_status === 'REJECTED' && <XCircle className="w-3 h-3 text-rose-600" />}
                        {c.verification_status === 'PENDING_REVIEW' && <Clock className="w-3 h-3 text-sky-600" />}
                        <span>{c.verification_status}</span>
                      </span>
                    </div>

                    <div className="text-slate-800 font-medium pt-1">
                      Requirement:{' '}
                      <span className="font-semibold text-brand-900">
                        {c.operator.toLowerCase().replace('_', ' ')} {JSON.stringify(c.canonical_value)}
                      </span>
                    </div>

                    {c.source_text && (
                      <div className="text-[11px] text-slate-500 italic bg-slate-50 p-2 rounded border border-slate-100">
                        "{c.source_text}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

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
