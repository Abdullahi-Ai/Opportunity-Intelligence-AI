import React, { useState } from 'react';
import { X, User, Save, Trash2, ShieldAlert } from 'lucide-react';
import { api } from '../api/client';

export default function ProfileModal({ isOpen, onClose, student, onProfileSaved, onProfileDeleted }) {
  const [formData, setFormData] = useState({
    email: student?.email || 'brian.kiprono@students.uonbi.ac.ke',
    full_name: student?.full_name || 'Brian Kiprono',
    university: student?.university || 'University of Nairobi',
    field_of_study: student?.field_of_study || 'Computer Science',
    degree_level: student?.degree_level || 'Undergraduate',
    year_of_study: student?.year_of_study || 3,
    county_of_origin: student?.county_of_origin || 'Uasin Gishu',
    gpa_or_grade: student?.gpa_or_grade || 'Second Class Upper (2:1)',
    preferred_categories: student?.preferred_categories || 'Internship, Graduate Trainee',
  });

  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const saved = await api.saveProfile(formData);
      onProfileSaved(saved);
      onClose();
    } catch (err) {
      alert('Failed to save profile: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete your profile and ALL tracked application records? This action cannot be undone (Kenya Data Protection Act compliance).`)) {
      return;
    }
    setDeleting(true);
    try {
      await api.deleteProfile(formData.email);
      onProfileDeleted();
      onClose();
    } catch (err) {
      alert('Delete failed: ' + err.message);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl max-w-lg w-full shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-brand-50 to-white">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-xs">
              <User className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-900">Student Preferences & Profile</h3>
              <p className="text-[11px] text-slate-500">Persisted in relational store for AI tailoring</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-full hover:bg-slate-100 text-slate-400">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-3.5 text-xs text-slate-700">
          <div>
            <label className="block text-slate-500 font-medium mb-1">Email Address</label>
            <input
              type="email"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-500 font-medium mb-1">Full Name</label>
              <input
                type="text"
                required
                value={formData.full_name}
                onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              />
            </div>

            <div>
              <label className="block text-slate-500 font-medium mb-1">University / College</label>
              <input
                type="text"
                required
                value={formData.university}
                onChange={(e) => setFormData({ ...formData, university: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-500 font-medium mb-1">Degree Level</label>
              <select
                value={formData.degree_level}
                onChange={(e) => setFormData({ ...formData, degree_level: e.target.value })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              >
                <option value="Undergraduate">Undergraduate</option>
                <option value="Diploma">Diploma</option>
                <option value="Masters">Masters</option>
                <option value="PhD">PhD</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-500 font-medium mb-1">Current Year of Study</label>
              <select
                value={formData.year_of_study}
                onChange={(e) => setFormData({ ...formData, year_of_study: parseInt(e.target.value, 10) })}
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              >
                <option value={1}>1st Year</option>
                <option value={2}>2nd Year</option>
                <option value={3}>3rd Year</option>
                <option value={4}>4th Year</option>
                <option value={5}>5th Year / Finalist</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-slate-500 font-medium mb-1">Field of Study / Course Major</label>
            <input
              type="text"
              required
              value={formData.field_of_study}
              onChange={(e) => setFormData({ ...formData, field_of_study: e.target.value })}
              placeholder="e.g. Computer Science, Mechanical Engineering"
              className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-500 font-medium mb-1">County of Origin</label>
              <input
                type="text"
                value={formData.county_of_origin}
                onChange={(e) => setFormData({ ...formData, county_of_origin: e.target.value })}
                placeholder="e.g. Nairobi, Kisumu, Bomet"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              />
            </div>

            <div>
              <label className="block text-slate-500 font-medium mb-1">Academic Grade / GPA</label>
              <input
                type="text"
                value={formData.gpa_or_grade}
                onChange={(e) => setFormData({ ...formData, gpa_or_grade: e.target.value })}
                placeholder="e.g. Upper Second (2:1) / B+"
                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:bg-white"
              />
            </div>
          </div>

          {/* Privacy Note */}
          <div className="p-3 bg-slate-50 rounded-xl border border-slate-200/80 text-[11px] text-slate-500 leading-relaxed flex items-start space-x-2">
            <ShieldAlert className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
            <span>
              Your profile is stored locally for eligibility matching and AI context tailoring. We never share your contact details with external recruiters.
            </span>
          </div>

          {/* Actions */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-100">
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs font-semibold text-rose-600 hover:text-rose-700 flex items-center space-x-1 p-2 rounded-lg hover:bg-rose-50"
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span>Delete Data</span>
            </button>

            <button
              type="submit"
              disabled={saving}
              className="flex items-center space-x-1.5 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl text-xs font-semibold shadow-sm"
            >
              <Save className="w-3.5 h-3.5" />
              <span>{saving ? 'Saving...' : 'Save Profile'}</span>
            </button>
          </div>
        </form>

      </div>
    </div>
  );
}
