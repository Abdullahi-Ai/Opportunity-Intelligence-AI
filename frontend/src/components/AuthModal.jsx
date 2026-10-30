import React, { useState } from 'react';
import { X, Lock, Mail, User, ShieldCheck, Key, LogIn, UserPlus } from 'lucide-react';
import { api, setToken } from '../api/client';

export default function AuthModal({ isOpen, onClose, user, onAuthSuccess, onLogout }) {
  const [isRegister, setIsRegister] = useState(false);
  const [role, setRole] = useState('student'); // 'student' or 'admin'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [adminSecret, setAdminSecret] = useState('');
  const [university, setUniversity] = useState('University of Nairobi');
  const [fieldOfStudy, setFieldOfStudy] = useState('Computer Science');
  const [degreeLevel, setDegreeLevel] = useState('Undergraduate');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (isRegister) {
        const payload = {
          email,
          password,
          full_name: fullName,
          role,
          admin_secret: role === 'admin' ? adminSecret : null,
          university: role === 'student' ? university : null,
          field_of_study: role === 'student' ? fieldOfStudy : null,
          degree_level: role === 'student' ? degreeLevel : null,
        };
        const res = await api.register(payload);
        setToken(res.access_token);
        onAuthSuccess(res.user);
        onClose();
      } else {
        const res = await api.login(email, password);
        setToken(res.access_token);
        onAuthSuccess(res.user);
        onClose();
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="relative bg-white rounded-3xl max-w-md w-full shadow-2xl border border-slate-100 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        
        {/* Header */}
        <div className="p-6 bg-gradient-to-r from-brand-700 to-brand-600 text-white flex justify-between items-center">
          <div className="flex items-center space-x-2.5">
            <div className="w-9 h-9 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="font-bold text-base">
                {user ? 'Account Management' : isRegister ? 'Create Your Account' : 'Sign In to Platform'}
              </h3>
              <p className="text-xs text-brand-100">
                {user ? user.email : 'Opportunity Intelligence AI for Kenya'}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-white/10 text-white/80 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {user ? (
            /* Authenticated User Profile Summary & Logout */
            <div className="space-y-4">
              <div className="p-4 rounded-2xl bg-slate-50 border border-slate-200/80 space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Account Role</span>
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    user.role === 'admin' ? 'bg-amber-100 text-amber-800 border border-amber-300' : 'bg-brand-100 text-brand-800'
                  }`}>
                    {user.role === 'admin' ? 'Verified Administrator' : 'University Student'}
                  </span>
                </div>
                <div>
                  <p className="text-sm font-bold text-slate-800">{user.full_name}</p>
                  <p className="text-xs text-slate-600">{user.email}</p>
                </div>
                {user.student_profile && (
                  <div className="pt-2 border-t border-slate-200 text-xs text-slate-600 space-y-0.5">
                    <p><span className="font-semibold text-slate-700">Institution:</span> {user.student_profile.university}</p>
                    <p><span className="font-semibold text-slate-700">Course:</span> {user.student_profile.field_of_study}</p>
                  </div>
                )}
              </div>

              <button
                onClick={() => {
                  setToken(null);
                  onLogout();
                  onClose();
                }}
                className="w-full py-2.5 px-4 bg-rose-50 hover:bg-rose-100 text-rose-700 font-semibold text-xs rounded-xl border border-rose-200 transition-colors"
              >
                Sign Out of This Device
              </button>
            </div>
          ) : (
            /* Login & Registration Form */
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                  {error}
                </div>
              )}

              {isRegister && (
                <>
                  {/* Role Selector */}
                  <div className="flex rounded-xl bg-slate-100 p-1 text-xs font-semibold">
                    <button
                      type="button"
                      onClick={() => setRole('student')}
                      className={`flex-1 py-1.5 rounded-lg transition-all ${
                        role === 'student' ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-600'
                      }`}
                    >
                      University Student
                    </button>
                    <button
                      type="button"
                      onClick={() => setRole('admin')}
                      className={`flex-1 py-1.5 rounded-lg transition-all ${
                        role === 'admin' ? 'bg-white text-amber-800 shadow-sm' : 'text-slate-600'
                      }`}
                    >
                      Administrator
                    </button>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 mb-1">Full Name</label>
                    <div className="relative">
                      <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                      <input
                        type="text"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                        placeholder="e.g. Amina Mohamed"
                        className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none"
                      />
                    </div>
                  </div>

                  {role === 'admin' ? (
                    <div>
                      <label className="block text-xs font-semibold text-amber-900 mb-1">
                        Administrator Verification Key <span className="text-rose-500">*</span>
                      </label>
                      <div className="relative">
                        <Key className="w-4 h-4 text-amber-600 absolute left-3 top-3" />
                        <input
                          type="password"
                          required
                          value={adminSecret}
                          onChange={(e) => setAdminSecret(e.target.value)}
                          placeholder="Enter verified secret key"
                          className="w-full bg-amber-50/50 border border-amber-300 rounded-xl pl-9 pr-3 py-2 text-xs focus:ring-2 focus:ring-amber-500 focus:outline-none"
                        />
                      </div>
                      <p className="text-[10px] text-slate-500 mt-1">
                        Required to certify administrator privileges. Verified against server security config.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">University</label>
                        <input
                          type="text"
                          value={university}
                          onChange={(e) => setUniversity(e.target.value)}
                          placeholder="e.g. UoN, Strathmore, JKUAT"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-700 mb-1">Field of Study</label>
                        <input
                          type="text"
                          value={fieldOfStudy}
                          onChange={(e) => setFieldOfStudy(e.target.value)}
                          placeholder="e.g. Computer Science"
                          className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none"
                        />
                      </div>
                    </div>
                  )}
                </>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="student@university.ac.ke"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-2 text-xs focus:ring-2 focus:ring-brand-500 focus:outline-none"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 px-4 bg-gradient-to-r from-brand-600 to-brand-700 hover:from-brand-700 hover:to-brand-800 text-white font-semibold text-xs rounded-xl shadow-md transition-all flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                {loading ? (
                  <span>Authenticating...</span>
                ) : isRegister ? (
                  <>
                    <UserPlus className="w-4 h-4" />
                    <span>Complete Registration</span>
                  </>
                ) : (
                  <>
                    <LogIn className="w-4 h-4" />
                    <span>Sign In</span>
                  </>
                )}
              </button>

              <div className="text-center pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setIsRegister(!isRegister);
                    setError(null);
                  }}
                  className="text-xs text-brand-600 hover:text-brand-800 font-medium"
                >
                  {isRegister ? 'Already have an account? Sign in' : "Don't have an account? Register here"}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
