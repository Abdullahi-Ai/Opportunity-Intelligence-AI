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
  FileText,
  RotateCcw,
  Flag,
  Check
} from 'lucide-react';
import { api } from '../api/client';

export default function AdminPortalModal({ isOpen, onClose, opportunities, onOpportunityUpdated }) {
  const [editingOpp, setEditingOpp] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [activeTab, setActiveTab] = useState('form'); // 'form' | 'history' | 'criteria'
  const [verificationHistory, setVerificationHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Stage 2.2B-3: Criteria Management State
  const [criteriaList, setCriteriaList] = useState([]);
  const [criteriaLoading, setCriteriaLoading] = useState(false);
  const [activeCritModal, setActiveCritModal] = useState(null); // { type: 'verify'|'reject'|'flag'|'reopen', crit }
  const [critInputUrl, setCritInputUrl] = useState('');
  const [critInputNotes, setCritInputNotes] = useState('');
  const [critHistoryLogs, setCritHistoryLogs] = useState(null);
  const [isAddingCriterion, setIsAddingCriterion] = useState(false);
  const [newCrit, setNewCrit] = useState({
    criterion_type: 'MINIMUM_ACADEMIC_GRADE',
    operator: 'GTE',
    criterion_value: 'UPPER_SECOND',
    is_mandatory: true,
    source_text: '',
    evidence_url: '',
  });

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
    setActiveTab('form');
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
    setActiveTab('form');
    const verStatus = opp.verification_status || (opp.is_verified ? 'VERIFIED' : 'UNVERIFIED');
    setFormData({
      title: opp.title,
      provider: opp.provider,
      category: opp.category,
      target_audience: opp.target_audience || '',
      fields_of_study: opp.fields_of_study || '',
      degree_levels: opp.degree_levels || '',
      official_url: opp.official_url || '',
      application_deadline: opp.application_deadline || '',
      is_verified: opp.is_verified || false,
      verification_status: verStatus,
      verification_date: opp.verification_date || '',
      source_notes: opp.source_notes || '',
      status: opp.status || 'open',
    });
    setError(null);
  };

  const loadCriteria = async (oppId) => {
    setCriteriaLoading(true);
    setError(null);
    try {
      const data = await api.adminGetOpportunityCriteria(oppId);
      setCriteriaList(data);
    } catch (err) {
      setError(err?.message || 'Failed to load criteria');
    } finally {
      setCriteriaLoading(false);
    }
  };

  const handleLoadHistory = async (oppId) => {
    setHistoryLoading(true);
    try {
      const history = await api.adminGetVerificationHistory(oppId);
      setVerificationHistory(history);
    } catch (err) {
      console.error("Failed to load verification history", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    if (formData.verification_status === 'VERIFIED') {
      if (!formData.official_url || !formData.official_url.trim()) {
        setError("Evidence standard violated: An opportunity marked as VERIFIED must include a valid official source URL.");
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
      setActiveTab('form');
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
        setActiveTab('form');
      }
    } catch (err) {
      alert(`Delete error: ${err.message}`);
    }
  };

  // Criteria Actions
  const handleVerifyCritSubmit = async (e) => {
    e.preventDefault();
    if (!critInputUrl.trim() || !critInputNotes.trim()) {
      alert("Verification requires both an authoritative evidence URL and review notes.");
      return;
    }
    try {
      await api.adminVerifyCriterion(activeCritModal.crit.id, {
        evidence_url: critInputUrl.trim(),
        evidence_notes: critInputNotes.trim(),
      });
      setActiveCritModal(null);
      setCritInputUrl('');
      setCritInputNotes('');
      loadCriteria(editingOpp.id);
    } catch (err) {
      alert(`Verification error: ${err.message}`);
    }
  };

  const handleRejectCritSubmit = async (e) => {
    e.preventDefault();
    if (!critInputNotes.trim()) {
      alert("Rejection requires review notes justifying why the requirement was rejected.");
      return;
    }
    try {
      await api.adminRejectCriterion(activeCritModal.crit.id, {
        evidence_notes: critInputNotes.trim(),
      });
      setActiveCritModal(null);
      setCritInputNotes('');
      loadCriteria(editingOpp.id);
    } catch (err) {
      alert(`Rejection error: ${err.message}`);
    }
  };

  const handleFlagCritSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.adminFlagCriterion(activeCritModal.crit.id, {
        evidence_notes: critInputNotes.trim() || "Flagged for further administrative review.",
      });
      setActiveCritModal(null);
      setCritInputNotes('');
      loadCriteria(editingOpp.id);
    } catch (err) {
      alert(`Flagging error: ${err.message}`);
    }
  };

  const handleReopenCritSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.adminReopenCriterion(activeCritModal.crit.id, {
        reason: critInputNotes.trim() || "Reopened by administrator.",
      });
      setActiveCritModal(null);
      setCritInputNotes('');
      loadCriteria(editingOpp.id);
    } catch (err) {
      alert(`Reopen error: ${err.message}`);
    }
  };

  const handleCreateCriterionSubmit = async (e) => {
    e.preventDefault();
    if (!newCrit.source_text.trim() || !newCrit.criterion_value.trim()) {
      alert("Source excerpt and canonical value are mandatory.");
      return;
    }
    try {
      await api.adminCreateCriterion(editingOpp.id, {
        ...newCrit,
        evidence_url: newCrit.evidence_url.trim() || editingOpp.official_url,
      });
      setIsAddingCriterion(false);
      setNewCrit({
        criterion_type: 'MINIMUM_ACADEMIC_GRADE',
        operator: 'GTE',
        criterion_value: 'UPPER_SECOND',
        is_mandatory: true,
        source_text: '',
        evidence_url: '',
      });
      loadCriteria(editingOpp.id);
    } catch (err) {
      alert(`Failed to create criterion: ${err.message}`);
    }
  };

  const handleViewCritHistory = async (crit) => {
    try {
      const logs = await api.adminGetCriterionHistory(crit.id);
      setCritHistoryLogs({ crit, logs });
    } catch (err) {
      alert(`Failed to fetch criterion history: ${err.message}`);
    }
  };

  const renderStatusBadge = (opp) => {
    const statusVal = opp.verification_status || (opp.is_verified ? 'VERIFIED' : 'UNVERIFIED');
    switch (statusVal) {
      case 'VERIFIED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            <span>Verified</span>
          </span>
        );
      case 'PENDING_REVIEW':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-100 text-sky-800">
            <Clock className="w-3 h-3 text-sky-600" />
            <span>Pending Review</span>
          </span>
        );
      case 'NEEDS_REVIEW':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800">
            <AlertCircle className="w-3 h-3 text-amber-600" />
            <span>Needs Review</span>
          </span>
        );
      case 'REJECTED':
        return (
          <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-100 text-rose-800">
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

  const renderCritStatusBadge = (statusVal) => {
    switch (statusVal) {
      case 'VERIFIED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 flex items-center space-x-1"><Check className="w-3 h-3" /><span>Verified</span></span>;
      case 'NEEDS_REVIEW':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-800 flex items-center space-x-1"><AlertCircle className="w-3 h-3" /><span>Needs Review</span></span>;
      case 'REJECTED':
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-100 text-rose-800 flex items-center space-x-1"><XCircle className="w-3 h-3" /><span>Rejected</span></span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-100 text-sky-800 flex items-center space-x-1"><Clock className="w-3 h-3" /><span>Pending</span></span>;
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
              <p className="text-xs text-slate-500">Curate verified records, inspect audit history, and enforce structured criteria standards</p>
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

          {/* Right Column: Editor Form, Criteria, or Audit History */}
          <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-5">
            {isCreating || editingOpp ? (
              <div className="space-y-4">
                
                {/* Mode Selector Tabs */}
                <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      onClick={() => setActiveTab('form')}
                      className={`text-xs font-bold px-2.5 py-1 rounded-lg transition-colors ${
                        activeTab === 'form' ? 'bg-amber-100 text-amber-900' : 'text-slate-500 hover:text-slate-700'
                      }`}
                    >
                      {isCreating ? 'New Opportunity' : 'Edit Details'}
                    </button>
                    {editingOpp && (
                      <>
                        <button
                          type="button"
                          onClick={() => {
                            setActiveTab('criteria');
                            loadCriteria(editingOpp.id);
                          }}
                          className={`text-xs font-bold px-2.5 py-1 rounded-lg transition-colors flex items-center space-x-1 ${
                            activeTab === 'criteria' ? 'bg-amber-100 text-amber-900' : 'text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          <ShieldCheck className="w-3.5 h-3.5" />
                          <span>Criteria</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActiveTab('history');
                            handleLoadHistory(editingOpp.id);
                          }}
                          className={`text-xs font-bold px-2.5 py-1 rounded-lg transition-colors flex items-center space-x-1 ${
                            activeTab === 'history' ? 'bg-amber-100 text-amber-900' : 'text-slate-500 hover:text-slate-700'
                          }`}
                        >
                          <History className="w-3.5 h-3.5" />
                          <span>Audit Log</span>
                        </button>
                      </>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setEditingOpp(null);
                      setActiveTab('form');
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

                {/* TAB 1: CRITERIA WORKFLOW (Stage 2.2B-3) */}
                {activeTab === 'criteria' && editingOpp ? (
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <h5 className="font-bold text-xs text-slate-800 flex items-center space-x-1">
                        <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                        <span>Structured Eligibility Criteria ({criteriaList.length})</span>
                      </h5>
                      <button
                        type="button"
                        onClick={() => setIsAddingCriterion(!isAddingCriterion)}
                        className="text-xs font-semibold px-2 py-1 bg-amber-600 text-white rounded-lg flex items-center space-x-1"
                      >
                        <Plus className="w-3 h-3" />
                        <span>Add Criterion</span>
                      </button>
                    </div>

                    {/* Inline Form to Add Criterion */}
                    {isAddingCriterion && (
                      <form onSubmit={handleCreateCriterionSubmit} className="p-3 bg-white rounded-xl border border-amber-300 space-y-2 text-xs">
                        <div className="font-bold text-slate-800">Add Manual Eligibility Criterion</div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] text-slate-500 font-bold">Category</label>
                            <select
                              value={newCrit.criterion_type}
                              onChange={(e) => setNewCrit({ ...newCrit, criterion_type: e.target.value })}
                              className="w-full text-xs p-1.5 border border-slate-200 rounded"
                            >
                              <option value="MINIMUM_ACADEMIC_GRADE">MINIMUM_ACADEMIC_GRADE</option>
                              <option value="KCSE_GRADE">KCSE_GRADE</option>
                              <option value="NUMERIC_GPA">NUMERIC_GPA</option>
                              <option value="COUNTY_RESTRICTION">COUNTY_RESTRICTION</option>
                              <option value="GEOGRAPHIC_ALLOCATION">GEOGRAPHIC_ALLOCATION</option>
                              <option value="GRADUATION_YEAR_RANGE">GRADUATION_YEAR_RANGE</option>
                              <option value="MONTHS_SINCE_GRADUATION">MONTHS_SINCE_GRADUATION</option>
                              <option value="EXPECTED_GRADUATION_WINDOW">EXPECTED_GRADUATION_WINDOW</option>
                              <option value="ACADEMIC_STANDING">ACADEMIC_STANDING</option>
                              <option value="OTHER">OTHER</option>
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] text-slate-500 font-bold">Operator</label>
                            <select
                              value={newCrit.operator}
                              onChange={(e) => setNewCrit({ ...newCrit, operator: e.target.value })}
                              className="w-full text-xs p-1.5 border border-slate-200 rounded"
                            >
                              <option value="GTE">GTE (&ge;)</option>
                              <option value="LTE">LTE (&le;)</option>
                              <option value="EQ">EQ (==)</option>
                              <option value="IN">IN</option>
                              <option value="BETWEEN">BETWEEN</option>
                            </select>
                          </div>
                        </div>
                        <div>
                          <label className="text-[10px] text-slate-500 font-bold">Value (e.g. UPPER_SECOND, 3.2, Turkana)</label>
                          <input
                            type="text"
                            value={newCrit.criterion_value}
                            onChange={(e) => setNewCrit({ ...newCrit, criterion_value: e.target.value })}
                            className="w-full text-xs p-1.5 border border-slate-200 rounded"
                            placeholder="Canonical value"
                            required
                          />
                        </div>
                        <div>
                          <label className="text-[10px] text-slate-500 font-bold">Verbatim Source Excerpt</label>
                          <textarea
                            value={newCrit.source_text}
                            onChange={(e) => setNewCrit({ ...newCrit, source_text: e.target.value })}
                            className="w-full text-xs p-1.5 border border-slate-200 rounded"
                            rows={2}
                            placeholder="Exact sentence from posting"
                            required
                          />
                        </div>
                        <div className="flex items-center space-x-2">
                          <label className="flex items-center space-x-1 text-[11px] font-semibold text-slate-700">
                            <input
                              type="checkbox"
                              checked={newCrit.is_mandatory}
                              onChange={(e) => setNewCrit({ ...newCrit, is_mandatory: e.target.checked })}
                            />
                            <span>Mandatory Requirement (vs Desirable)</span>
                          </label>
                        </div>
                        <div className="flex justify-end space-x-2 pt-1">
                          <button
                            type="button"
                            onClick={() => setIsAddingCriterion(false)}
                            className="px-2 py-1 text-slate-500 hover:text-slate-700"
                          >
                            Cancel
                          </button>
                          <button
                            type="submit"
                            className="px-3 py-1 bg-amber-600 text-white rounded font-bold"
                          >
                            Save Criterion
                          </button>
                        </div>
                      </form>
                    )}

                    {/* Criteria List */}
                    {criteriaLoading ? (
                      <div className="py-8 text-center text-xs text-slate-400">Loading criteria...</div>
                    ) : criteriaList.length === 0 ? (
                      <div className="py-8 text-center text-xs text-slate-400 bg-white rounded-xl border border-slate-200">
                        No structured criteria currently registered for this opportunity.
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1">
                        {criteriaList.map((crit) => (
                          <div key={crit.id} className="p-3 bg-white rounded-xl border border-slate-200 text-xs space-y-1.5">
                            <div className="flex justify-between items-start">
                              <div>
                                <span className="font-bold text-slate-900">{crit.criterion_type}</span>
                                <span className="ml-2 font-mono text-[11px] text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                                  {crit.operator} {crit.criterion_value}
                                </span>
                              </div>
                              <div className="flex items-center space-x-1.5">
                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${crit.is_mandatory ? 'bg-indigo-50 text-indigo-700 border border-indigo-200' : 'bg-slate-100 text-slate-600'}`}>
                                  {crit.is_mandatory ? 'Mandatory' : 'Desirable'}
                                </span>
                                {renderCritStatusBadge(crit.verification_status)}
                              </div>
                            </div>

                            <p className="text-[11px] text-slate-600 italic bg-slate-50 p-1.5 rounded border border-slate-100">
                              &ldquo;{crit.source_text}&rdquo;
                            </p>

                            {crit.evidence_url && (
                              <p className="text-[10px] text-brand-700 truncate font-mono">
                                Evidence: {crit.evidence_url}
                              </p>
                            )}

                            {/* Action Buttons */}
                            <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[10px]">
                              <button
                                type="button"
                                onClick={() => handleViewCritHistory(crit)}
                                className="text-slate-500 hover:text-amber-700 flex items-center space-x-1"
                              >
                                <History className="w-3 h-3" />
                                <span>Audit Log</span>
                              </button>
                              <div className="flex space-x-1.5">
                                {crit.verification_status !== 'VERIFIED' ? (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveCritModal({ type: 'verify', crit });
                                        setCritInputUrl(crit.evidence_url || editingOpp.official_url || '');
                                        setCritInputNotes('');
                                      }}
                                      className="px-2 py-0.5 bg-emerald-600 text-white rounded hover:bg-emerald-700 font-bold"
                                    >
                                      Verify
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveCritModal({ type: 'reject', crit });
                                        setCritInputNotes('');
                                      }}
                                      className="px-2 py-0.5 bg-rose-600 text-white rounded hover:bg-rose-700 font-bold"
                                    >
                                      Reject
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setActiveCritModal({ type: 'flag', crit });
                                        setCritInputNotes('');
                                      }}
                                      className="px-2 py-0.5 bg-amber-500 text-white rounded hover:bg-amber-600 font-bold"
                                    >
                                      Flag
                                    </button>
                                  </>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setActiveCritModal({ type: 'reopen', crit });
                                      setCritInputNotes('');
                                    }}
                                    className="px-2 py-0.5 bg-slate-600 text-white rounded hover:bg-slate-700 font-bold flex items-center space-x-1"
                                  >
                                    <RotateCcw className="w-3 h-3" />
                                    <span>Reopen</span>
                                  </button>
                                )}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : activeTab === 'history' && editingOpp ? (
                  /* TAB 2: OPPORTUNITY-LEVEL AUDIT HISTORY */
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
                  /* TAB 3: OPPORTUNITY EDIT FORM */
                  <form onSubmit={handleSubmit} className="space-y-3">
                    <div className="flex items-center justify-between pb-1">
                      <h5 className="font-bold text-xs text-slate-800">
                        {isCreating ? 'Create Opportunity' : `Edit: ${editingOpp.title}`}
                      </h5>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Title</label>
                      <input
                        type="text"
                        required
                        value={formData.title}
                        onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                        className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                        placeholder="e.g. Equity Wings to Fly Scholarship"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Provider</label>
                        <input
                          type="text"
                          required
                          value={formData.provider}
                          onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                          className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                          placeholder="e.g. Equity Group Foundation"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Category</label>
                        <select
                          value={formData.category}
                          onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                          className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                        >
                          <option value="Scholarship">Scholarship</option>
                          <option value="Internship">Internship</option>
                          <option value="Graduate Trainee">Graduate Trainee</option>
                          <option value="Fellowship">Fellowship</option>
                          <option value="Competition">Competition</option>
                        </select>
                      </div>
                    </div>

                    <div className="p-3 bg-amber-50/60 rounded-xl border border-amber-200/80 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-bold text-amber-950 flex items-center space-x-1">
                          <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
                          <span>Certification & Verification Status</span>
                        </label>
                      </div>

                      <select
                        value={formData.verification_status}
                        onChange={(e) => setFormData({ ...formData, verification_status: e.target.value })}
                        className="w-full text-xs px-3 py-2 border border-amber-300 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white font-semibold"
                      >
                        <option value="UNVERIFIED">UNVERIFIED (Default Ingestion State)</option>
                        <option value="PENDING_REVIEW">PENDING_REVIEW (Queued for Administrator Review)</option>
                        <option value="NEEDS_REVIEW">NEEDS_REVIEW (Flagged for Discrepancy)</option>
                        <option value="VERIFIED">VERIFIED (Source Cross-Checked with Primary Official URL)</option>
                        <option value="REJECTED">REJECTED (Defunct, Fraudulent, or Expired Record)</option>
                      </select>
                      <p className="text-[10px] text-amber-800 leading-tight">
                        * In accordance with Phase 1 standards, marking a record as VERIFIED requires a verifiable public official URL and appends to the immutable audit trail.
                      </p>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Official Verification URL</label>
                      <input
                        type="url"
                        value={formData.official_url}
                        onChange={(e) => setFormData({ ...formData, official_url: e.target.value })}
                        className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white font-mono"
                        placeholder="https://official.provider.ke/careers"
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Application Deadline</label>
                        <input
                          type="text"
                          value={formData.application_deadline}
                          onChange={(e) => setFormData({ ...formData, application_deadline: e.target.value })}
                          className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                          placeholder="e.g. 2026-12-31"
                        />
                      </div>
                      <div>
                        <label className="block text-[11px] font-bold text-slate-700 mb-1">Status</label>
                        <select
                          value={formData.status}
                          onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                          className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                        >
                          <option value="open">Open</option>
                          <option value="closed">Closed</option>
                          <option value="archived">Archived</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-[11px] font-bold text-slate-700 mb-1">Source Notes & Review Rationale</label>
                      <textarea
                        rows={2}
                        value={formData.source_notes}
                        onChange={(e) => setFormData({ ...formData, source_notes: e.target.value })}
                        className="w-full text-xs px-3 py-2 border border-slate-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-amber-500 bg-white"
                        placeholder="Explain verification evidence, source circular, or modification justification..."
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

      {/* CRITERION ACTION MODAL (Verify / Reject / Flag / Reopen) */}
      {activeCritModal && (
        <div className="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-5 shadow-2xl border border-slate-200 space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-slate-100">
              <h4 className="font-bold text-sm text-slate-900 uppercase">
                {activeCritModal.type} Criterion: {activeCritModal.crit.criterion_type}
              </h4>
              <button onClick={() => setActiveCritModal(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-600">
              Criterion Requirement: <strong>{activeCritModal.crit.operator} {activeCritModal.crit.criterion_value}</strong>
            </p>

            {activeCritModal.type === 'verify' && (
              <form onSubmit={handleVerifyCritSubmit} className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Authoritative Evidence URL *</label>
                  <input
                    type="url"
                    value={critInputUrl}
                    onChange={(e) => setCritInputUrl(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg font-mono text-xs"
                    placeholder="https://official.provider.ke/guidelines.pdf"
                    required
                  />
                </div>
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Administrative Audit Notes *</label>
                  <textarea
                    rows={3}
                    value={critInputNotes}
                    onChange={(e) => setCritInputNotes(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                    placeholder="Document primary source cross-reference and verification rationale..."
                    required
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button type="button" onClick={() => setActiveCritModal(null)} className="px-3 py-1.5 text-slate-500">
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold">
                    Confirm Verification
                  </button>
                </div>
              </form>
            )}

            {activeCritModal.type === 'reject' && (
              <form onSubmit={handleRejectCritSubmit} className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Rejection Reason *</label>
                  <textarea
                    rows={3}
                    value={critInputNotes}
                    onChange={(e) => setCritInputNotes(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                    placeholder="Document why this requirement was rejected (e.g. non-factual, hallmarked by hallucination)..."
                    required
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button type="button" onClick={() => setActiveCritModal(null)} className="px-3 py-1.5 text-slate-500">
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-bold">
                    Confirm Rejection
                  </button>
                </div>
              </form>
            )}

            {activeCritModal.type === 'flag' && (
              <form onSubmit={handleFlagCritSubmit} className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Reason for Flagging (Needs Review) *</label>
                  <textarea
                    rows={3}
                    value={critInputNotes}
                    onChange={(e) => setCritInputNotes(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                    placeholder="Note discrepancy, ambiguity, or secondary verification needed..."
                    required
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button type="button" onClick={() => setActiveCritModal(null)} className="px-3 py-1.5 text-slate-500">
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg font-bold">
                    Flag Criterion
                  </button>
                </div>
              </form>
            )}

            {activeCritModal.type === 'reopen' && (
              <form onSubmit={handleReopenCritSubmit} className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-slate-700 mb-1">Justification for Reopening *</label>
                  <textarea
                    rows={3}
                    value={critInputNotes}
                    onChange={(e) => setCritInputNotes(e.target.value)}
                    className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                    placeholder="State reason for reopening previously reviewed criterion..."
                    required
                  />
                </div>
                <div className="flex justify-end space-x-2 pt-2">
                  <button type="button" onClick={() => setActiveCritModal(null)} className="px-3 py-1.5 text-slate-500">
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-1.5 bg-slate-700 hover:bg-slate-800 text-white rounded-lg font-bold">
                    Reopen to Pending
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* CRITERION AUDIT LOG MODAL */}
      {critHistoryLogs && (
        <div className="fixed inset-0 z-60 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full p-5 shadow-2xl border border-slate-200 space-y-3 max-h-[80vh] flex flex-col">
            <div className="flex justify-between items-center pb-2 border-b border-slate-100">
              <h4 className="font-bold text-sm text-slate-900 flex items-center space-x-1.5">
                <History className="w-4 h-4 text-amber-600" />
                <span>Immutable Criterion Audit Log</span>
              </h4>
              <button onClick={() => setCritHistoryLogs(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs bg-slate-50 p-2 rounded-lg border border-slate-100">
              <strong>{critHistoryLogs.crit.criterion_type}:</strong> {critHistoryLogs.crit.operator} {critHistoryLogs.crit.criterion_value}
            </div>

            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {critHistoryLogs.logs.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-400">No audit events recorded.</div>
              ) : (
                critHistoryLogs.logs.map((log) => (
                  <div key={log.id} className="p-2.5 bg-white rounded-xl border border-slate-200 text-xs space-y-1">
                    <div className="flex justify-between items-center text-[11px] text-slate-500">
                      <span className="font-semibold text-slate-700">{log.admin_email || 'System / Auto'}</span>
                      <span>{new Date(log.created_at).toLocaleString()}</span>
                    </div>
                    <div className="flex items-center space-x-2 font-mono text-[11px]">
                      <span className="px-1.5 py-0.5 bg-slate-100 text-slate-700 rounded font-bold">{log.event_type}</span>
                      <span>{log.previous_status} &rarr; <strong>{log.new_status}</strong></span>
                    </div>
                    {log.evidence_notes && (
                      <p className="text-[11px] text-slate-600 italic bg-slate-50 p-1.5 rounded border border-slate-100">
                        &ldquo;{log.evidence_notes}&rdquo;
                      </p>
                    )}
                    {log.evidence_url && (
                      <p className="text-[10px] text-brand-700 truncate font-mono">
                        URL: {log.evidence_url}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
