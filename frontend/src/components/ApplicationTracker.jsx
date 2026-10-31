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
  RefreshCw 
} from 'lucide-react';
import { api } from '../api/client';

export default function ApplicationTracker({ student, onOpenAssistant }) {
  const [applications, setApplications] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeStageFilter, setActiveStageFilter] = useState('All');
  const [newTaskText, setNewTaskText] = useState({});

  const loadTrackerData = async () => {
    if (!student?.id) return;
    setLoading(true);
    try {
      const [appsData, statsData] = await Promise.all([
        api.getTrackedApplications(student.id),
        api.getDashboardStats(student.id).catch(() => null),
      ]);
      setApplications(appsData);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to load application tracker data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTrackerData();
  }, [student]);

  const handleStageChange = async (appId, newStage) => {
    try {
      await api.updateApplicationStage(appId, newStage);
      setApplications((prev) =>
        prev.map((app) => (app.id === appId ? { ...app, stage: newStage } : app))
      );
      loadTrackerData();
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
            checklists: app.checklists.map((t) =>
              t.id === taskId ? { ...t, is_completed: res.is_completed } : t
            ),
          };
        })
      );
      loadTrackerData();
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
            checklists: [...app.checklists, created],
          };
        })
      );
      setNewTaskText((prev) => ({ ...prev, [appId]: '' }));
      loadTrackerData();
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
            checklists: app.checklists.filter((t) => t.id !== taskId),
          };
        })
      );
      loadTrackerData();
    } catch (err) {
      console.error('Delete task failed:', err);
    }
  };

  const handleRemoveOpportunity = async (oppId) => {
    if (!confirm('Are you sure you want to remove this opportunity from your tracker?')) return;
    try {
      await api.removeTrackedApplication(student.id, oppId);
      setApplications((prev) => prev.filter((a) => a.opportunity_id !== oppId));
      loadTrackerData();
    } catch (err) {
      alert('Failed to remove opportunity');
    }
  };

  const filteredApps = applications.filter((app) => {
    if (activeStageFilter === 'All') return true;
    return app.stage === activeStageFilter;
  });

  return (
    <div className="space-y-6">
      
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center font-bold">
              <BookmarkCheck className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase">Tracked</p>
              <p className="text-xl font-extrabold text-slate-900">{stats.total_saved}</p>
            </div>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center font-bold">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase">Drafting / Prep</p>
              <p className="text-xl font-extrabold text-slate-900">{stats.in_progress}</p>
            </div>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
              <CheckCircle2 className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase">Submitted</p>
              <p className="text-xl font-extrabold text-slate-900">{stats.submitted}</p>
            </div>
          </div>

          <div className="p-4 bg-white rounded-2xl border border-slate-200 shadow-sm flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[11px] font-semibold text-slate-500 uppercase">Task Readiness</p>
              <p className="text-xl font-extrabold text-slate-900">{stats.checklist_completion_rate}%</p>
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <div className="flex items-center space-x-1.5 p-1 bg-white rounded-xl border border-slate-200 text-xs">
          {['All', 'Saved', 'Drafting', 'Submitted'].map((stage) => (
            <button
              key={stage}
              onClick={() => setActiveStageFilter(stage)}
              className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                activeStageFilter === stage
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {stage}
            </button>
          ))}
        </div>

        <button
          onClick={loadTrackerData}
          className="flex items-center space-x-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-xl text-xs font-medium text-slate-600 hover:bg-slate-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      {loading ? (
        <div className="py-12 text-center text-slate-500 text-sm">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto text-brand-600 mb-2" />
          <p>Loading your tracked applications and checklists...</p>
        </div>
      ) : filteredApps.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-3xl border border-slate-200 p-8 space-y-3">
          <BookmarkCheck className="w-12 h-12 text-slate-300 mx-auto" />
          <h3 className="font-bold text-base text-slate-800">No applications in this view</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Discover opportunities from our verified Kenyan directory and click <strong>"Track"</strong> to automatically generate your application preparation checklist.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredApps.map((app) => {
            const completedCount = app.checklists.filter((t) => t.is_completed).length;
            const totalCount = app.checklists.length;
            const progressPct = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

            return (
              <div
                key={app.id}
                className="bg-white rounded-3xl border border-slate-200 p-6 shadow-sm hover:shadow-md transition-all space-y-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-700">
                      ID: {app.opportunity_id}
                    </span>
                    <h3 className="text-base font-bold text-slate-900 mt-1">
                      {app.opportunity?.title || app.opportunity_id.replace('opp-', '').replace(/-/g, ' ').toUpperCase()}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {app.opportunity?.provider || 'Verified Partner'}
                    </p>
                  </div>

                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-slate-500 font-medium">Stage:</span>
                    <select
                      value={app.stage}
                      onChange={(e) => handleStageChange(app.id, e.target.value)}
                      className="text-xs font-semibold px-3 py-1.5 rounded-xl border border-slate-200 bg-slate-50 focus:ring-2 focus:ring-brand-500"
                    >
                      <option value="Saved">Saved</option>
                      <option value="Drafting">Drafting</option>
                      <option value="Submitted">Submitted</option>
                      <option value="Interview">Interview</option>
                      <option value="Accepted">Accepted</option>
                      <option value="Rejected">Rejected</option>
                    </select>

                    <button
                      onClick={() => handleRemoveOpportunity(app.opportunity_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
                      title="Remove from tracker"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div>
                  <div className="flex justify-between text-xs text-slate-500 mb-1">
                    <span>Preparation Checklist Progress</span>
                    <span className="font-semibold text-slate-800">
                      {completedCount} / {totalCount} completed ({progressPct}%)
                    </span>
                  </div>
                  <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 transition-all duration-300"
                      style={{ width: `${progressPct}%` }}
                    />
                  </div>
                </div>

                <div className="space-y-2 pt-1">
                  {app.checklists.map((task) => (
                    <div
                      key={task.id}
                      className="flex items-start justify-between p-2.5 rounded-xl bg-slate-50 hover:bg-slate-100/80 transition-colors text-xs group"
                    >
                      <button
                        onClick={() => handleToggleTask(app.id, task.id)}
                        className="flex items-start space-x-2.5 text-left flex-1"
                      >
                        {task.is_completed ? (
                          <CheckSquare className="w-4 h-4 text-emerald-600 mt-0.5 flex-shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                        )}
                        <span
                          className={`leading-relaxed ${
                            task.is_completed ? 'line-through text-slate-400' : 'text-slate-700 font-medium'
                          }`}
                        >
                          {task.task_description}
                        </span>
                      </button>

                      <button
                        onClick={() => handleDeleteTask(app.id, task.id)}
                        className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-600 p-1 transition-opacity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}

                  <div className="flex items-center space-x-2 pt-2">
                    <input
                      type="text"
                      value={newTaskText[app.id] || ''}
                      onChange={(e) =>
                        setNewTaskText((prev) => ({ ...prev, [app.id]: e.target.value }))
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleAddTask(app.id);
                      }}
                      placeholder="Add a custom preparation task (e.g. Request Dean endorsement letter)..."
                      className="flex-1 bg-white border border-slate-200 rounded-xl px-3 py-1.5 text-xs focus:ring-2 focus:ring-brand-500"
                    />
                    <button
                      onClick={() => handleAddTask(app.id)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-900 text-white rounded-xl text-xs font-semibold flex items-center space-x-1"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add</span>
                    </button>
                  </div>
                </div>

              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
