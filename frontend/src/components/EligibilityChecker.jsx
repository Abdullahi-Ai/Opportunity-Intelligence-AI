import React, { useState, useEffect } from 'react';
import { X, Sparkles, CheckCircle2, AlertCircle, XCircle, ArrowRight, RefreshCw } from 'lucide-react';
import { api } from '../api/client';

export default function EligibilityChecker({ opportunity, student, onClose, onSave, isTracked }) {
  const [degreeLevel, setDegreeLevel] = useState(student?.degree_level || 'Undergraduate');
  const [fieldOfStudy, setFieldOfStudy] = useState(student?.field_of_study || 'Computer Science');
  const [yearOfStudy, setYearOfStudy] = useState(student?.year_of_study || 3);
  const [kcseGrade, setKcseGrade] = useState(student?.gpa_or_grade || 'B+');
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const runAssessment = async () => {
    if (!opportunity) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.assessEligibility({
        opportunity_id: opportunity.id,
        student_degree_level: degreeLevel,
        student_field_of_study: fieldOfStudy,
        student_year_of_study: parseInt(yearOfStudy, 10),
        student_kcse_grade: kcseGrade,
      });
      setResult(data);
    } catch (err) {
      setError(err.message || 'Assessment failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runAssessment();
  }, [opportunity]);

  if (!opportunity) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-xl w-full max-h-[90vh] flex flex-col shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        <div className="p-6 border-b border-slate-100 flex items-start justify-between bg-gradient-to-r from-amber-500/10 via-brand-500/5 to-white">
          <div>
            <div className="flex items-center space-x-2 text-xs font-semibold text-amber-700 mb-1">
              <Sparkles className="w-4 h-4 text-amber-500" />
              <span>Deterministic Eligibility Evaluator</span>
            </div>
            <h2 className="text-lg font-bold text-slate-900">{opportunity.title}</h2>
            <p className="text-xs text-slate-500">{opportunity.provider}</p>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-slate-100 text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-5 text-xs text-slate-700">
          
          <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 space-y-3">
            <span className="font-bold text-[11px] uppercase tracking-wider text-slate-400 block">
              Evaluated Against Your Attributes:
            </span>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-slate-500 mb-1">Degree Level</label>
                <select
                  value={degreeLevel}
                  onChange={(e) => setDegreeLevel(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-brand-500"
                >
                  <option value="Undergraduate">Undergraduate</option>
                  <option value="Diploma">Diploma</option>
                  <option value="Masters">Masters</option>
                  <option value="PhD">PhD</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-500 mb-1">Year of Study</label>
                <select
                  value={yearOfStudy}
                  onChange={(e) => setYearOfStudy(e.target.value)}
                  className="w-full bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-brand-500"
                >
                  <option value={1}>Year 1</option>
                  <option value={2}>Year 2</option>
                  <option value={3}>Year 3</option>
                  <option value={4}>Year 4</option>
                  <option value={5}>Year 5 / Graduated</option>
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-slate-500 mb-1">Field of Study / Major</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={fieldOfStudy}
                    onChange={(e) => setFieldOfStudy(e.target.value)}
                    placeholder="e.g. Computer Science, Civil Engineering"
                    className="flex-1 bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs focus:ring-2 focus:ring-brand-500"
                  />
                  <button
                    onClick={runAssessment}
                    disabled={loading}
                    className="px-3 py-1.5 bg-brand-600 text-white rounded-lg font-medium hover:bg-brand-700 flex items-center space-x-1"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                    <span>Re-evaluate</span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          {loading && (
            <div className="py-6 text-center text-slate-500 space-y-2">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-brand-600" />
              <p>Evaluating published criteria against student parameters...</p>
            </div>
          )}

          {result && !loading && (
            <div className="space-y-4">
              
              <div
                className={`p-4 rounded-2xl border flex items-start space-x-3 ${
                  result.overall_assessment.includes('Likely Eligible')
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                    : result.overall_assessment.includes('Needs Verification')
                    ? 'bg-amber-50 border-amber-200 text-amber-900'
                    : 'bg-rose-50 border-rose-200 text-rose-900'
                }`}
              >
                {result.overall_assessment.includes('Likely Eligible') ? (
                  <CheckCircle2 className="w-6 h-6 text-emerald-600 flex-shrink-0 mt-0.5" />
                ) : result.overall_assessment.includes('Needs Verification') ? (
                  <AlertCircle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
                ) : (
                  <XCircle className="w-6 h-6 text-rose-600 flex-shrink-0 mt-0.5" />
                )}
                <div>
                  <h4 className="font-bold text-sm">{result.overall_assessment}</h4>
                  <p className="text-xs opacity-90 mt-0.5">
                    {result.disclaimer}
                  </p>
                </div>
              </div>

              <div>
                <h4 className="font-bold text-xs uppercase tracking-wider text-slate-400 mb-2">
                  Criterion-by-Criterion Verification:
                </h4>
                <div className="space-y-2">
                  {result.criteria_breakdown.map((crit, idx) => (
                    <div
                      key={idx}
                      className="p-3 bg-white rounded-xl border border-slate-200 flex items-center justify-between gap-3"
                    >
                      <div>
                        <span className="font-bold text-slate-800 text-xs block">{crit.criterion}</span>
                        <span className="text-[11px] text-slate-500 block">
                          Required: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-700">{crit.required || 'Any'}</code>
                        </span>
                        <span className="text-[11px] text-slate-500 block">
                          Provided: <code className="bg-slate-100 px-1 py-0.5 rounded text-slate-700">{crit.provided}</code>
                        </span>
                      </div>
                      <div>
                        <span
                          className={`text-[11px] font-bold px-2 py-1 rounded-full ${
                            crit.status === 'Meets'
                              ? 'bg-emerald-100 text-emerald-800'
                              : crit.status === 'Needs Verification'
                              ? 'bg-amber-100 text-amber-800'
                              : 'bg-rose-100 text-rose-800'
                          }`}
                        >
                          {crit.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

            </div>
          )}

        </div>

        <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800"
          >
            Close
          </button>
          
          <button
            onClick={() => {
              onClose();
              onSave(opportunity);
            }}
            disabled={isTracked}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              isTracked
                ? 'bg-emerald-100 text-emerald-800 cursor-default'
                : 'bg-brand-600 hover:bg-brand-700 text-white shadow-sm'
            }`}
          >
            {isTracked ? 'Already in Tracker' : 'Save & Build Checklist'}
          </button>
        </div>

      </div>
    </div>
  );
}
