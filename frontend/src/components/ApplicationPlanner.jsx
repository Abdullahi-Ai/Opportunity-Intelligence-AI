import React, { useState, useEffect } from 'react';
import { 
  BookmarkCheck, 
  Calendar, 
  CheckSquare, 
  Square, 
  Trash2, 
  Plus, 
  ExternalLink, 
  AlertCircle, 
  Clock, 
  CheckCircle2, 
  Sparkles,
  RefreshCw,
  FileText,
  Edit3,
  Save,
  Filter,
  Layers,
  ChevronRight,
  TrendingUp,
  Award,
  Search
} from 'lucide-react';
import { api } from '../api/client';

export default function ApplicationPlanner({ 
  student, 
  user,
  onOpenAssistant, 
  onNavigateToExplore,
  onOpenAuth 
}) {
  const [applications, setApplications] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeStageFilter, setActiveStageFilter] = useState('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [newTaskText, setNewTaskText] = useState({});
  const [notesState, setNotesState] = useState({});
  const [savingNotes, setSavingNotes] = useState({});
  const [targetDates, setTargetDates] = useState({});

  const stages = ['All', 'Saved', 'Drafting', 'Submitted', 'Interview', 'Accepted', 'Rejected'];

  const loadPlannerData = async () => {
    if (!student?.id && !user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const studentId = student?.id || user?.id;
      const [appsData, statsData] = await Promise.all([
        api.getTrackedApplications(studentId).catch(() => []),
        api.getDashboardStats(studentId).catch(() => null),
      ]);
      setApplications(appsData || []);
      setStats(statsData);

      const notesMap = {};
      const datesMap = {};
      (appsData || []).forEach((app) => {
        notesMap[app.id] = app.notes || '';
        datesMap[app.id] = app.target_submission_date || '';
      });
      setNotesState(notesMap);
      setTargetDates(datesMap);
    } catch (err) {
      console.error('Failed to load application planner data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlannerData();
  }, [student, user]);

  const handleStageChange = async (appId, newStage) => {
    try {
      await api.updateApplicationStage(appId, newStage);
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, stage: newStage } : app))
      );
      const studentId = student?.id || user?.id;
      api.getDashboardStats(studentId).then(setStats).catch(() => {});
    } catch (err) {
      alert('Failed to update application stage');
    }
  };

  const handleToggleTask = async (appId, taskId) => {
    try {
      const res = await api.toggleChecklistTask(taskId);
      setApplications((prev) =>
        prev.map((app) => {
          if (app.id !== appId) return app;
          return {
            ...app,
            checklists: (app.checklists || []).map((t) =>
              t.id === taskId ? { ...t, is_completed: res.is_completed } : t
            ),
          };
        })
      );
      const studentId = student?.id || user?.id;
      api.getDashboardStats(studentId).then(setStats).catch(() => {});
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  };

  const handleAddTask = async (appId) => {
    const text = newTaskText[appId];
    if (!text || !text.trim()) return;

    try {
      const created = await api.addCustomChecklistTask(appId, text.trim());
      setApplications((prev) =>
        prev.map((app) => {
          if (app.id !== appId) return app;
          return {
            ...app,
            checklists: [...(app.checklists || []), created],
          };
        })
      );
      setNewTaskText((prev) => ({ ...prev, [appId]: '' }));
      const studentId = student?.id || user?.id;
      api.getDashboardStats(studentId).then(setStats).catch(() => {});
    } catch (err) {
      alert('Failed to add custom checklist task');
    }
  };

  const handleDeleteTask = async (appId, taskId) => {
    try {
      await api.deleteChecklistTask(taskId);
      setApplications((prev) =>
        prev.map((app) => {
          if (app.id !== appId) return app;
          return {
            ...app,
            checklists: (app.checklists || []).filter((t) => t.id !== taskId),
          };
        })
      );
      const studentId = student?.id || user?.id;
      api.getDashboardStats(studentId).then(setStats).catch(() => {});
    } catch (err) {
      alert('Failed to delete checklist task');
    }
  };

  const handleSaveNotes = async (appId) => {
    setSavingNotes((prev) => ({ ...prev, [appId]: true }));
    try {
      const text = notesState[appId] || '';
      await api.updateApplicationNotes(appId, text);
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, notes: text } : app))
      );
    } catch (err) {
      alert('Failed to save notes');
    } finally {
      setSavingNotes((prev) => ({ ...prev, [appId]: false }));
    }
  };

  const handleUpdateTargetDate = async (appId, dateStr) => {
    setTargetDates((prev) => ({ ...prev, [appId]: dateStr }));
    try {
      await api.updateApplicationTargetDate(appId, dateStr || null);
    } catch (err) {
      console.error('Failed to update target date:', err);
    }
  };

  const handleGenerateChecklist = async (appId) => {
    try {
      await api.generateChecklistForTrackedApp(appId);
      loadPlannerData();
    } catch (err) {
      alert('Failed to regenerate checklist');
    }
  };

  const handleRemoveApplication = async (opportunityId) => {
    if (!window.confirm('Remove this application and its checklist from your planner?')) return;
    try {
      const studentId = student?.id || user?.id;
      await api.removeTrackedApplication(studentId, opportunityId);
      setApplications((prev) => prev.filter((app) => app.opportunity_id !== opportunityId));
      loadPlannerData();
    } catch (err) {
      alert('Failed to remove application');
    }
  };

  if (!user && !student) {
    return (
      <div className="bg-white rounded-3xl p-12 border border-slate-200/80 text-center max-w-xl mx-auto space-y-5 animate-in fade-in duration-200">
        <div className="w-16 h-16 rounded-3xl bg-brand-50 border border-brand-200 text-brand-600 flex items-center justify-center mx-auto shadow-sm">
          <BookmarkCheck className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <h3 className="text-xl font-black text-slate-900 tracking-tight">Application Planner</h3>
          <p className="text-xs sm:text-sm text-slate-500 leading-relaxed">
            Sign in with your student account to manage application lifecycles, monitor preparation checklists, track deadlines, and organize your document submissions.
          </p>
        </div>
        <button
          onClick={onOpenAuth}
          className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs rounded-xl shadow-md transition-colors"
        >
          Sign In to Access Planner
        </button>
      </div>
    );
  }

  const filteredApplications = applications.filter((app) => {
    if (activeStageFilter !== 'All' && app.stage !== activeStageFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const title = app.opportunity?.title?.toLowerCase() || '';
      const prov = app.opportunity?.provider?.toLowerCase() || '';
      if (!title.includes(q) && !prov.includes(q)) return false;
    }
    return true;
  });

  return (
    <div className="space-y-6 animate-in fade-in duration-200">
      
      <div className="bg-gradient-to-r from-slate-900 via-brand-950 to-slate-900 rounded-3xl p-6 sm:p-8 text-white shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div className="space-y-2 max-w-xl">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-400/10 border border-emerald-400/30 text-emerald-300 text-[11px] font-bold uppercase tracking-wider">
            <BookmarkCheck className="w-3.5 h-3.5" />
            <span>Interactive Application Tracking</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-black tracking-tight">
            Application Planner Workspace
          </h2>
          <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
            Manage your submissions, track required documents, take preparation notes, and never miss closing dates with deterministic countdowns.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row gap-2.5 flex-shrink-0">
          <button
            onClick={onNavigateToExplore}
            className="px-4 py-2 rounded-xl bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs shadow-sm transition-colors flex items-center justify-center space-x-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Discover Opportunities</span>
          </button>
          <button
            onClick={loadPlannerData}
            disabled={loading}
            className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white font-semibold text-xs border border-white/20 transition-colors flex items-center justify-center space-x-1.5 disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Saved in Planner</p>
            <p className="text-2xl font-black text-slate-900 mt-1">{stats.total_saved}</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Drafting / In Progress</p>
            <p className="text-2xl font-black text-amber-600 mt-1">{stats.in_progress}</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Submitted</p>
            <p className="text-2xl font-black text-emerald-600 mt-1">{stats.submitted}</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Tasks Complete</p>
            <p className="text-2xl font-black text-brand-600 mt-1">{stats.checklist_completion_rate}%</p>
            <p className="text-[10px] text-slate-400 mt-0.5">{stats.completed_checklist_tasks} of {stats.total_checklist_tasks} items</p>
          </div>
          <div className="bg-white p-4 rounded-2xl border border-slate-200/80 shadow-2xs">
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">Closing Soon (&lt;14d)</p>
            <p className={`text-2xl font-black mt-1 ${stats.urgent_deadlines_count > 0 ? 'text-rose-600' : 'text-slate-900'}`}>
              {stats.urgent_deadlines_count}
            </p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl p-4 border border-slate-200/80 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
          {stages.map((stage) => {
            const isActive = activeStageFilter === stage;
            const count = stage === 'All' ? applications.length : applications.filter((a) => a.stage === stage).length;
            return (
              <button
                key={stage}
                onClick={() => setActiveStageFilter(stage)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all whitespace-nowrap flex items-center space-x-1.5 ${
                  isActive
                    ? 'bg-slate-900 text-white shadow-2xs'
                    : 'bg-slate-50 text-slate-600 hover:bg-slate-100'
                }`}
              >
                <span>{stage}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-700'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        <div className="relative min-w-[220px]">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search tracked applications..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-9 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
      </div>

      {loading ? (
        <div className="space-y-4 py-8">
          {[1, 2].map((i) => (
            <div key={i} className="bg-white rounded-3xl p-6 border border-slate-200/80 animate-pulse space-y-4">
              <div className="h-5 bg-slate-100 rounded w-1/3" />
              <div className="h-4 bg-slate-100 rounded w-1/4" />
              <div className="h-20 bg-slate-50 rounded" />
            </div>
          ))}
        </div>
      ) : filteredApplications.length === 0 ? (
        <div className="bg-white rounded-3xl p-12 border border-slate-200/80 text-center space-y-4">
          <BookmarkCheck className="w-10 h-10 text-slate-400 mx-auto" />
          <h4 className="font-extrabold text-slate-900 text-base">No Applications Found</h4>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            {activeStageFilter !== 'All'
              ? `You do not have any applications marked as '${activeStageFilter}'.`
              : 'You have not saved any opportunities to your planner yet.'}
          </p>
          <button
            onClick={onNavigateToExplore}
            className="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm transition-colors"
          >
            Explore Verified Opportunities
          </button>
        </div>
      ) : (
        <div className="space-y-5">
          {filteredApplications.map((app) => {
            const opp = app.opportunity || {};
            const checklists = app.checklists || [];
            const completedCount = checklists.filter((t) => t.is_completed).length;
            const progressPercent = checklists.length > 0 ? Math.round((completedCount / checklists.length) * 100) : 0;
            const isClosingSoon = opp.days_remaining !== null && opp.days_remaining >= 0 && opp.days_remaining <= 14;

            return (
              <div
                key={app.id}
                className="bg-white rounded-3xl border border-slate-200/80 shadow-2xs hover:border-brand-200 transition-all overflow-hidden"
              >
                <div className="p-6 space-y-5">
                  
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-extrabold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700 tracking-wide">
                          {opp.category || 'Opportunity'}
                        </span>
                        {opp.deadline_status_label && (
                          <span className={`inline-flex items-center space-x-1 text-[10px] font-bold px-2 py-0.5 rounded-md ${
                            isClosingSoon ? 'bg-rose-50 text-rose-700 border border-rose-200' : 'bg-slate-50 text-slate-600 border border-slate-200'
                          }`}>
                            <Clock className="w-3 h-3" />
                            <span>{opp.deadline_status_label}</span>
                          </span>
                        )}
                      </div>
                      <h3 className="font-black text-slate-900 text-lg leading-snug">
                        {opp.title || 'Tracked Opportunity'}
                      </h3>
                      <p className="text-xs font-medium text-slate-500">{opp.provider || 'Verified Organization'}</p>
                    </div>

                    <div className="flex items-center space-x-3 flex-shrink-0">
                      <div className="flex flex-col items-end">
                        <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">Stage</label>
                        <select
                          value={app.stage}
                          onChange={(e) => handleStageChange(app.id, e.target.value)}
                          className="bg-slate-50 border border-slate-200 rounded-xl px-3 py-1.5 text-xs font-bold text-slate-800 focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-2xs"
                        >
                          {stages.filter((s) => s !== 'All').map((stage) => (
                            <option key={stage} value={stage}>{stage}</option>
                          ))}
                        </select>
                      </div>

                      <button
                        onClick={() => handleRemoveApplication(app.opportunity_id)}
                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-xl transition-colors mt-4 sm:mt-0"
                        title="Remove from planner"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                          <CheckSquare className="w-4 h-4 text-brand-600" />
                          <span>Preparation Checklist</span>
                        </span>
                        <span className="text-[11px] font-bold text-slate-500">
                          {completedCount} of {checklists.length} done ({progressPercent}%)
                        </span>
                      </div>

                      <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden">
                        <div
                          className="bg-emerald-500 h-full transition-all duration-300"
                          style={{ width: `${progressPercent}%` }}
                        />
                      </div>

                      <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                        {checklists.map((task) => (
                          <div
                            key={task.id}
                            className={`flex items-start justify-between p-2 rounded-xl text-xs transition-colors ${
                              task.is_completed ? 'bg-white/80 line-through text-slate-400' : 'bg-white text-slate-800 shadow-2xs'
                            }`}
                          >
                            <button
                              onClick={() => handleToggleTask(app.id, task.id)}
                              className="flex items-start space-x-2 text-left flex-1"
                            >
                              {task.is_completed ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                              ) : (
                                <Square className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                              )}
                              <span className="leading-snug">{task.task_description}</span>
                            </button>
                            <button
                              onClick={() => handleDeleteTask(app.id, task.id)}
                              className="text-slate-300 hover:text-rose-500 ml-2 p-0.5 transition-colors"
                              title="Delete task"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="flex items-center space-x-2 pt-1">
                        <input
                          type="text"
                          placeholder="Add custom preparation step..."
                          value={newTaskText[app.id] || ''}
                          onChange={(e) => setNewTaskText({ ...newTaskText, [app.id]: e.target.value })}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleAddTask(app.id); }}
                          className="flex-1 bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                        <button
                          onClick={() => handleAddTask(app.id)}
                          className="p-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-xl transition-colors"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      {checklists.length === 0 && (
                        <button
                          onClick={() => handleGenerateChecklist(app.id)}
                          className="w-full py-1.5 text-[11px] font-bold text-brand-700 bg-brand-50 hover:bg-brand-100 rounded-xl transition-colors flex items-center justify-center space-x-1.5"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Generate Checklist from Official Requirements</span>
                        </button>
                      )}
                    </div>

                    <div className="bg-slate-50 border border-slate-200/80 rounded-2xl p-4 space-y-3 flex flex-col justify-between">
                      <div className="space-y-3">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-slate-900 flex items-center space-x-1.5">
                            <Edit3 className="w-4 h-4 text-brand-600" />
                            <span>My Notes & Strategy</span>
                          </span>
                          <button
                            onClick={() => handleSaveNotes(app.id)}
                            disabled={savingNotes[app.id]}
                            className="text-[11px] font-bold text-brand-600 hover:text-brand-700 flex items-center space-x-1"
                          >
                            <Save className="w-3 h-3" />
                            <span>{savingNotes[app.id] ? 'Saving...' : 'Save Notes'}</span>
                          </button>
                        </div>

                        <textarea
                          rows={4}
                          value={notesState[app.id] || ''}
                          onChange={(e) => setNotesState({ ...notesState, [app.id]: e.target.value })}
                          placeholder="Record personal deadlines, contact person, document draft links, or interview notes..."
                          className="w-full bg-white border border-slate-200 rounded-xl p-2.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                        />
                      </div>

                      <div className="pt-2 border-t border-slate-200/60 flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Calendar className="w-3.5 h-3.5 text-slate-400" />
                          <span className="text-[11px] font-bold text-slate-600">Target Submission:</span>
                        </div>
                        <input
                          type="date"
                          value={targetDates[app.id] || ''}
                          onChange={(e) => handleUpdateTargetDate(app.id, e.target.value)}
                          className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-xs text-slate-800 font-semibold focus:outline-none focus:ring-2 focus:ring-brand-500"
                        />
                      </div>
                    </div>
                  </div>

                </div>

                <div className="px-6 py-3.5 bg-slate-50/60 border-t border-slate-100 flex items-center justify-between gap-4">
                  <button
                    onClick={() => onOpenAssistant(`I am working on my application for '${opp.title}'. What should I prepare next?`)}
                    className="text-xs font-semibold text-brand-700 hover:text-brand-800 flex items-center space-x-1.5"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                    <span>Ask AI Advisor for Document & Submission Guidance</span>
                  </button>

                  {opp.official_url && (
                    <a
                      href={opp.official_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center space-x-1 text-xs font-bold text-slate-700 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-2xs hover:bg-slate-50 transition-colors"
                    >
                      <span>Official Submission Portal</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
