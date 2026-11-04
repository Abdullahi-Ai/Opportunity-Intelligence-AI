import React, { useState } from 'react';
import { 
  X, 
  ShieldCheck, 
  Plus, 
  Edit2, 
  Trash2, 
  CheckCircle2, 
  AlertCircle, 
  Save, 
  ExternalLink,
  Clock,
  History,
  ShieldAlert,
  XCircle,
  FileText
} from 'lucide-react';
import { api } from '../api/client';

export default function AdminPortalModal({ isOpen, onClose, opportunities, onOpportunityUpdated }) {
  const [editingOpp, setEditingOpp] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [verificationHistory, setVerificationHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [formData, setFormData] = useState({
    title: '',
    provider: '',
    category: 'Scholarship',
    target_audience: 'Kenyan University Students',
    fields_of_study: 'All Fields',
    degree_levels: 'Undergraduate, Postgraduate',
    official_url: '',
    application_deadline: '',
    is_verified: false,
    verification_status: 'UNVERIFIED',
    verification_date: '',
    source_notes: '',
    status: 'open',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleStartCreate = () => {
    setEditingOpp(null);
    setIsCreating(true);
    setShowHistory(false);
    setFormData({
      title: '',
      provider: '',
      category: 'Scholarship',
      target_audience: 'Kenyan University Students',
      fields_of_study: 'All Fields',
      degree_levels: 'Undergraduate, Postgraduate',
      official_url: '',
      application_deadline: '',
      is_verified: false,
      verification_status: 'UNVERIFIED',
      verification_date: '',
      source_notes: '',
      status: 'open',
    });
    setError(null);
  };

  const handleStartEdit = (opp) => {
    setIsCreating(false);
    setEditingOpp(opp);
    setShowHistory(false);
    const verStatus = opp.verification_status || (opp.is_verified ? 'VERIFIED' : 'UNVERIFIED');
    setFormData({
      title: opp.title,
      provider: opp.provider,
      category: opp.category,
      target_audience: opp.target_audience || '',
      fields_of_study: opp.fields_of_study || '',
      degree_levels: opp.degree_levels || '',
      official_url: opp.official_url,
      application_deadline: opp.application_deadline || '',
      is_verified: verStatus === 'VERIFIED',
      verification_status: verStatus,
      verification_date: opp.verification_date || '',
      source_notes: opp.source_notes || '',
      status: opp.status || 'open',
    });
    setError(null);
  };

  const handleLoadHistory = async (oppId) => {
    setHistoryLoading(true);
    setShowHistory(true);
    try {
      const history = await api.adminGetVerificationHistory(oppId);
      setVerificationHistory(history || []);
    } catch (err) {
      console.error('Failed to load verification history:', err);
      setVerificationHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Client-side verification validation
    if (formData.verification_status === 'VERIFIED') {
      if (!formData.official_url || !formData.official_url.match(/^https?:\/\//i)) {
        setError('A valid official URL starting with http:// or https:// is required to certify as VERIFIED.');
        setLoading(false);
        return;
      }
      if (!formData.source_notes || formData.source_notes.trim().length < 10) {
        setError('Verification evidence notes must be at least 10 characters documenting proof.');
        setLoading(false);
        return;
      }
    }

    try {
      const payload = {
        ...formData,
        is_verified: formData.verification_status === 'VERIFIED'
      };

      if (isCreating) {
        await api.adminCreateOpportunity(payload);
      } else if (editingOpp) {
        // If status changed or verification updated, call verify endpoint for auditable logging
        const origStatus = editingOpp.verification_status || (editingOpp.is_verified ? 'VERIFIED' : 'UNVERIFIED');
        if (payload.verification_status !== origStatus) {
          await api.adminVerifyOpportunity(editingOpp.id, {
            status: payload.verification_status,
            official_source_url: payload.official_url,
            evidence_notes: payload.source_notes || `Status updated from ${origStatus} to ${payload.verification_status}.`
          });
        }
        await api.adminUpdateOpportunity(editingOpp.id, payload);
      }
      onOpportunityUpdated();
      setEditingOpp(null);
      setIsCreating(false);
      setShowHistory(false);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to save opportunity');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (oppId) => {
    if (!window.confirm(`Are you sure you want to delete this opportunity? This cannot be undone.`)) return;
    try {
      await api.adminDeleteOpportunity(oppId);
      onOpportunityUpdated();
      if (editingOpp?.id === oppId) {
        setEditingOpp(null);
        setIsCreating(false);
        setShowHistory(false);
      }
    } catch (err) {
      alert(`Delete error: ${err.message}`);
    }
  };

  const renderStatusBadge = (opp) => {
    const status = opp.verification_status || (opp.is_verified ? 'VERIFIED' : 'UNVERIFIED');
    switch (status) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
            <ShieldCheck className="w-3 h-3 text-emerald-600" />
            <span>Verified</span>
          </span>
        );
      case 'NEEDS_REVIEW':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
            <AlertCircle className="w-3 h-3 text-amber-600" />
            <span>Needs Review</span>
          </span>
        );
      case 'PENDING_REVIEW':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800 border border-sky-200">
            <Clock className="w-3 h-3 text-sky-600" />
            <span>Pending Review</span>
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800 border border-rose-200">
            <XCircle className="w-3 h-3 text-rose-600" />
            <span>Rejected</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-200 text-slate-700">
            <ShieldAlert className="w-3 h-3 text-slate-500" />
            <span>Unverified</span>
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-5xl w-full max-h-[92vh] flex flex-col shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-slate-900">Administrator Opportunity Management Portal</h3>
              <p className="text-xs text-slate-500">Curate verified records, inspect audit history, and enforce evidence standards</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-2 rounded-full hover:bg-slate-200/60 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body Grid */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          
          {/* Left Column: Directory List */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-bold text-sm text-slate-800">
                Managed Opportunities ({opportunities.length})
              </h4>
              <button
                onClick={handleStartCreate}
                className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl text-xs font-bold transition-colors flex items-center space-x-1 shadow-2xs"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Opportunity</span>
              </button>
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {opportunities.map((opp) => (
                <div
                  key={opp.id}
                  className={`p-3 rounded-2xl border transition-all ${
                    editingOpp?.id === opp.id
                      ? 'border-amber-500 bg-amber-50/30 shadow-xs'
                      : 'border-slate-200/80 bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-bold text-xs text-slate-900 truncate">{opp.title}</p>
                      <p className="text-[11px] text-slate-500 truncate">{opp.provider}</p>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => handleStartEdit(opp)}
                        className="p-1 text-slate-500 hover:text-amber-600 rounded hover:bg-amber-100"
                        title="Edit Opportunity"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => handleDelete(opp.id)}
                        className="p-1 text-slate-500 hover:text-rose-600 rounded hover:bg-rose-100"
                        title="Delete Opportunity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  <div className="mt-2 pt-2 border-t border-slate-200/60 flex items-center justify-between text-[11px]">
                    {renderStatusBadge(opp)}
                    <span className="text-slate-500 font-medium text-[11px]">
                      Deadline: {opp.application_deadline || 'Rolling'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Column: Editor Form or Audit History */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-5">
            {isCreating || editingOpp ? (
              <div className="space-y-4">
                
                {/* Mode Selector Tabs (Edit Form vs Audit History) */}
                <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      onClick={() => setShowHistory(false)}
                      className={`text-xs font-bold px-2.5 py-1 rounded-lg transition-colors ${
                        !showHistory ? 'bg-amber-100 text-amber-900' : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {isCreating ? 'New Opportunity' : 'Edit Details'}
                    </button>
                    {editingOpp && (
                      <button
                        type="button"
                        onClick={() => handleLoadHistory(editingOpp.id)}
                        className={`text-xs font-bold px-2.5 py-1 rounded-lg transition-colors flex items-center space-x-1 ${
                          showHistory ? 'bg-amber-100 text-amber-900' : 'text-slate-500 hover:text-slate-700'
                        }`}
                      >
                        <History className="w-3.5 h-3.5" />
                        <span>Audit History</span>
                      </button>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setEditingOpp(null);
                      setShowHistory(false);
                    }}
                    className="text-slate-400 hover:text-slate-600 text-xs"
                  >
                    Cancel
                  </button>
                </div>

                {error && (
                  <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                    {error}
                  </div>
                )}

                {showHistory ? (
                  /* Verification Audit History View */
                  <div className="space-y-3">
                    <h5 className="font-bold text-xs text-slate-800 flex items-center space-x-1.5">
                      <FileText className="w-3.5 h-3.5 text-amber-600" />
                      <span>Traceable Verification History: {editingOpp.title}</span>
                    </h5>

                    {historyLoading ? (
                      <div className="py-8 text-center text-xs text-slate-400">Loading audit trail...</div>
                    ) : verificationHistory.length === 0 ? (
                      <div className="py-8 text-center text-xs text-slate-400 bg-white rounded-xl border border-slate-200">
                        No historical verification decisions logged yet for this record.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
                        {verificationHistory.map((log) => (
                          <div key={log.id} className="p-3 bg-white rounded-xl border border-slate-200 text-xs space-y-1.5">
                            <div className="flex justify-between items-center text-[11px] text-slate-500">
                              <span className="font-semibold text-slate-700">{log.admin_email || 'Administrator'}</span>
                              <span>{new Date(log.created_at).toLocaleString()}</span>
                            </div>
                            <div className="flex items-center space-x-1.5 text-xs font-bold">
                              <span className="text-slate-500">{log.previous_status}</span>
                              <span>&rarr;</span>
                              <span className={log.new_status === 'VERIFIED' ? 'text-emerald-700' : 'text-amber-700'}>
                                {log.new_status}
                              </span>
                            </div>
                            {log.official_source_url && (
                              <p className="text-[11px] text-brand-700 truncate font-mono">
                                Source: {log.official_source_url}
                              </p>
                            )}
                            <p className="text-[11px] text-slate-600 italic bg-slate-50 p-2 rounded-lg border border-slate-100">
                              &ldquo;{log.evidence_notes}&rdquo;
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  /* Opportunity Edit Form */
                  <form onSubmit={handleSave} className="space-y-3 text-xs">
                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Opportunity Title</label>
                      <input
                        type="text"
                        required
                        value={formData.title}
                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                        className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Provider / Organization</label>
                        <input
                          type="text"
                          required
                          value={formData.provider}
                          onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Category</label>
                        <select
                          value={formData.category}
                          onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        >
                          <option value="Scholarship">Scholarship</option>
                          <option value="Internship">Internship</option>
                          <option value="Graduate Trainee">Graduate Trainee</option>
                          <option value="Fellowship">Fellowship</option>
                          <option value="Competition">Competition</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">Official Source URL</label>
                      <input
                        type="url"
                        required
                        value={formData.official_url}
                        onChange={(e) => setFormData({ ...formData, official_url: e.target.value })}
                        placeholder="https://..."
                        className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Application Deadline</label>
                        <input
                          type="date"
                          value={formData.application_deadline}
                          onChange={(e) => setFormData({ ...formData, application_deadline: e.target.value })}
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block font-semibold text-slate-700 mb-1">Intake Status</label>
                        <select
                          value={formData.status}
                          onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        >
                          <option value="open">Open / Active</option>
                          <option value="closed">Closed / Past Deadline</option>
                        </select>
                      </div>
                    </div>

                    {/* Verification Status Selector */}
                    <div className="p-3 bg-white border border-slate-200 rounded-xl space-y-2">
                      <label className="block font-bold text-slate-900">
                        Authoritative Verification Status
                      </label>
                      <select
                        value={formData.verification_status}
                        onChange={(e) => setFormData({ ...formData, verification_status: e.target.value })}
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 font-bold focus:ring-2 focus:ring-amber-500 focus:outline-none"
                      >
                        <option value="UNVERIFIED">UNVERIFIED — Default / Unvetted Record</option>
                        <option value="PENDING_REVIEW">PENDING_REVIEW — Awaiting Admin Examination</option>
                        <option value="VERIFIED">VERIFIED — Evidence Authenticated by Admin</option>
                        <option value="NEEDS_REVIEW">NEEDS_REVIEW — Missing Criteria / Ambiguous</option>
                        <option value="REJECTED">REJECTED — Scams / Ineligible / Expired</option>
                      </select>
                      <p className="text-[11px] text-slate-500">
                        Certifying as <strong>VERIFIED</strong> strictly requires an authoritative official URL and documented verification notes.
                      </p>
                    </div>

                    <div>
                      <label className="block font-semibold text-slate-700 mb-1">
                        Evidence & Audit Notes
                      </label>
                      <textarea
                        rows={2}
                        value={formData.source_notes}
                        onChange={(e) => setFormData({ ...formData, source_notes: e.target.value })}
                        placeholder="Document verified official notice, Gazette publication, or direct portal confirmation"
                        className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                      />
                    </div>

                    <button
                      type="submit"
                      disabled={loading}
                      className="w-full mt-2 py-2.5 px-4 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded-xl shadow-md transition-colors flex items-center justify-center space-x-2 disabled:opacity-50"
                    >
                      <Save className="w-4 h-4" />
                      <span>{loading ? 'Saving to Database...' : 'Save Opportunity Record'}</span>
                    </button>
                  </form>
                )}

              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 space-y-2">
                <ShieldCheck className="w-10 h-10 text-amber-600/40" />
                <p className="font-medium text-slate-600">Select an opportunity to inspect or edit</p>
                <p className="text-[11px] max-w-xs text-slate-400">
                  Or click &ldquo;+ Add Opportunity&rdquo; to ingest newly announced scholarships, attachments, or competitions with evidence-based verification.
                </p>
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}
