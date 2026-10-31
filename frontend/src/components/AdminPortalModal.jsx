import React, { useState } from 'react';
import { X, ShieldCheck, Plus, Edit2, Trash2, CheckCircle2, AlertCircle, Save, ExternalLink } from 'lucide-react';
import { api } from '../api/client';

export default function AdminPortalModal({ isOpen, onClose, opportunities, onOpportunityUpdated }) {
  const [editingOpp, setEditingOpp] = useState(null);
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    provider: '',
    category: 'Scholarship',
    target_audience: 'Kenyan University Students',
    fields_of_study: 'All Fields',
    degree_levels: 'Undergraduate, Postgraduate',
    official_url: '',
    application_deadline: '',
    is_verified: true,
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
    setFormData({
      title: '',
      provider: '',
      category: 'Scholarship',
      target_audience: 'Kenyan University Students',
      fields_of_study: 'All Fields',
      degree_levels: 'Undergraduate, Postgraduate',
      official_url: '',
      application_deadline: '',
      is_verified: true,
      verification_date: new Date().toISOString().split('T')[0],
      source_notes: 'Verified against official institutional announcement portal.',
      status: 'open',
    });
    setError(null);
  };

  const handleStartEdit = (opp) => {
    setIsCreating(false);
    setEditingOpp(opp);
    setFormData({
      title: opp.title,
      provider: opp.provider,
      category: opp.category,
      target_audience: opp.target_audience || '',
      fields_of_study: opp.fields_of_study || '',
      degree_levels: opp.degree_levels || '',
      official_url: opp.official_url,
      application_deadline: opp.application_deadline || '',
      is_verified: opp.is_verified,
      verification_date: opp.verification_date || '',
      source_notes: opp.source_notes || 'Verified against official published guidelines.',
      status: opp.status || 'open',
    });
    setError(null);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isCreating) {
        await api.adminCreateOpportunity(formData);
      } else if (editingOpp) {
        await api.adminUpdateOpportunity(editingOpp.id, formData);
      }
      onOpportunityUpdated();
      setEditingOpp(null);
      setIsCreating(false);
    } catch (err) {
      setError(err.message || 'Failed to save opportunity');
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
      }
    } catch (err) {
      alert(`Delete error: ${err.message}`);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-3xl max-w-4xl w-full shadow-2xl border border-slate-100 overflow-hidden flex flex-col max-h-[90vh]">
        
        <div className="p-6 bg-gradient-to-r from-amber-700 to-amber-600 text-white flex justify-between items-center flex-shrink-0">
          <div className="flex items-center space-x-2.5">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            <div>
              <h3 className="font-bold text-lg">Verified Administrator Portal</h3>
              <p className="text-xs text-amber-100">
                Curate opportunity knowledge base, verify sources, and update deadlines
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleStartCreate}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-white text-amber-900 font-semibold text-xs hover:bg-amber-50 transition-colors shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>Add Opportunity</span>
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10 text-white/80 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
          
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Published Records ({opportunities.length})
            </h4>

            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {opportunities.map((opp) => (
                <div
                  key={opp.id}
                  className={`p-3 rounded-2xl border transition-all text-xs ${
                    editingOpp?.id === opp.id
                      ? 'border-amber-500 bg-amber-50/50 shadow-sm'
                      : 'border-slate-200 bg-slate-50 hover:bg-white hover:border-slate-300'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="font-bold text-slate-900 truncate">{opp.title}</p>
                      <p className="text-slate-500 text-[11px]">{opp.provider} • {opp.category}</p>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        onClick={() => handleStartEdit(opp)}
                        className="p-1 text-slate-500 hover:text-amber-700 rounded hover:bg-amber-100"
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
                    <span className={`px-2 py-0.5 rounded-full font-semibold ${
                      opp.is_verified ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-200 text-slate-700'
                    }`}>
                      {opp.is_verified ? 'Verified' : 'Unverified'}
                    </span>
                    <span className="text-slate-500 font-medium">
                      Deadline: {opp.application_deadline || 'Rolling'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-4">
            {isCreating || editingOpp ? (
              <form onSubmit={handleSave} className="space-y-3 text-xs">
                <div className="flex justify-between items-center pb-2 border-b border-slate-200">
                  <h4 className="font-bold text-sm text-slate-800">
                    {isCreating ? 'Ingest New Verified Opportunity' : `Edit: ${editingOpp.title}`}
                  </h4>
                  <button
                    type="button"
                    onClick={() => {
                      setIsCreating(false);
                      setEditingOpp(null);
                    }}
                    className="text-slate-400 hover:text-slate-600"
                  >
                    Cancel
                  </button>
                </div>

                {error && (
                  <div className="p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                    {error}
                  </div>
                )}

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
                      <option value="Internship">Internship / Attachment</option>
                      <option value="Graduate Trainee">Graduate Trainee</option>
                      <option value="Fellowship">Fellowship</option>
                      <option value="Competition">Competition / Grant</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Official Portal URL</label>
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
                      value={formData.application_deadline || ''}
                      onChange={(e) => setFormData({ ...formData, application_deadline: e.target.value })}
                      className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block font-semibold text-slate-700 mb-1">Status</label>
                    <select
                      value={formData.status}
                      onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                      className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                    >
                      <option value="open">Open</option>
                      <option value="upcoming">Upcoming</option>
                      <option value="closed">Closed / Expired</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Source Verification Notes</label>
                  <textarea
                    rows={2}
                    value={formData.source_notes}
                    onChange={(e) => setFormData({ ...formData, source_notes: e.target.value })}
                    placeholder="Document official notice, Gazette publication, or direct portal confirmation"
                    className="w-full bg-white border border-slate-200 rounded-xl px-3 py-1.5 focus:ring-2 focus:ring-amber-500 focus:outline-none"
                  />
                </div>

                <div className="flex items-center space-x-2 pt-1">
                  <input
                    type="checkbox"
                    id="is_verified"
                    checked={formData.is_verified}
                    onChange={(e) => setFormData({ ...formData, is_verified: e.target.checked })}
                    className="rounded text-amber-600 focus:ring-amber-500"
                  />
                  <label htmlFor="is_verified" className="font-semibold text-slate-700 cursor-pointer">
                    Certified by Administrator as Verified Source
                  </label>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full mt-2 py-2 px-4 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-xl shadow-md transition-colors flex items-center justify-center space-x-2 disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  <span>{loading ? 'Saving to Database...' : 'Save Opportunity Record'}</span>
                </button>
              </form>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 text-slate-400 space-y-2">
                <ShieldCheck className="w-10 h-10 text-amber-600/40" />
                <p className="font-medium text-slate-600">Select an opportunity to edit</p>
                <p className="text-[11px] max-w-xs">
                  Or click "+ Add Opportunity" to ingest newly announced scholarships, attachments, or competitions.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
