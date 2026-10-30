import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Filter, 
  Sparkles, 
  Compass, 
  BookmarkCheck, 
  Bot, 
  ShieldCheck, 
  RefreshCw, 
  AlertCircle 
} from 'lucide-react';
import { api, getToken, setToken } from './api/client';
import Navbar from './components/Navbar';
import OpportunityCard from './components/OpportunityCard';
import OpportunityModal from './components/OpportunityModal';
import EligibilityChecker from './components/EligibilityChecker';
import AIAssistantDrawer from './components/AIAssistantDrawer';
import ApplicationTracker from './components/ApplicationTracker';
import ProfileModal from './components/ProfileModal';
import AuthModal from './components/AuthModal';
import AdminPortalModal from './components/AdminPortalModal';

export default function App() {
  const [activeTab, setActiveTab] = useState('discover'); // 'discover' | 'tracker'
  
  // Data State
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [isOpenOnly, setIsOpenOnly] = useState(false);

  // Authenticated User & Profile State
  const [user, setUser] = useState(null);
  const [student, setStudent] = useState(null);
  const [trackedIds, setTrackedIds] = useState(new Set());

  // Modals & Drawers
  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [eligibilityOpportunity, setEligibilityOpportunity] = useState(null);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isAdminOpen, setIsAdminOpen] = useState(false);

  // Check current session on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = getToken();
      if (!token) return;
      try {
        const me = await api.getMe();
        handleAuthSuccess(me);
      } catch (err) {
        console.warn('Session expired or invalid:', err);
        setToken(null);
        setUser(null);
        setStudent(null);
      }
    };
    initAuth();
  }, []);

  const handleAuthSuccess = (authenticatedUser) => {
    setUser(authenticatedUser);
    if (authenticatedUser.student_profile) {
      setStudent({
        id: authenticatedUser.student_profile.id,
        email: authenticatedUser.email,
        full_name: authenticatedUser.full_name,
        university: authenticatedUser.student_profile.university,
        field_of_study: authenticatedUser.student_profile.field_of_study,
        degree_level: authenticatedUser.student_profile.degree_level,
        year_of_study: 3,
      });
    } else {
      setStudent({
        id: authenticatedUser.id,
        email: authenticatedUser.email,
        full_name: authenticatedUser.full_name,
        university: 'Kenyan Institution',
        field_of_study: 'General',
        degree_level: 'Undergraduate',
        year_of_study: 1,
      });
    }
  };

  const handleLogout = () => {
    setUser(null);
    setStudent(null);
    setTrackedIds(new Set());
  };

  // Load Opportunities
  const loadOpportunities = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getOpportunities({
        category: selectedCategory,
        search: searchQuery,
        is_open_only: isOpenOnly,
      });
      setOpportunities(data);
    } catch (err) {
      setError('Could not connect to the backend API. Please make sure the FastAPI server is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  // Sync Student Tracked IDs
  const syncTrackedIds = async () => {
    if (!student?.id) return;
    try {
      const tracked = await api.getTrackedApplications(student.id);
      setTrackedIds(new Set(tracked.map((a) => a.opportunity_id)));
    } catch (e) {
      console.warn('Tracked applications sync failed:', e);
    }
  };

  useEffect(() => {
    loadOpportunities();
  }, [selectedCategory, isOpenOnly]);

  useEffect(() => {
    syncTrackedIds();
  }, [student]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    loadOpportunities();
  };

  const handleSaveToTracker = async (opp) => {
    if (!user) {
      alert('Please sign in or create an account to save opportunities to your personal application tracker.');
      setIsAuthOpen(true);
      return;
    }

    try {
      await api.saveToTracker(student.id, opp.id, 'Saved', 'Saved via Opportunity Discovery Explorer');
      setTrackedIds((prev) => new Set([...prev, opp.id]));
      alert(`Success! "${opp.title}" has been saved to your Application Tracker and a preparation checklist has been created.`);
    } catch (err) {
      alert('Failed to save opportunity to tracker: ' + err.message);
    }
  };

  const categories = [
    { label: 'All Opportunities', value: '' },
    { label: 'Scholarships & Aid', value: 'Scholarship' },
    { label: 'Internships & Attachments', value: 'Internship' },
    { label: 'Graduate Trainee', value: 'Graduate Trainee' },
    { label: 'Fellowships', value: 'Fellowship' },
    { label: 'Competitions', value: 'Competition' },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-['Inter',sans-serif]">
      
      {/* Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        student={student}
        onOpenProfile={() => (user ? setIsProfileOpen(true) : setIsAuthOpen(true))}
        onOpenAssistant={() => setIsAssistantOpen(true)}
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenAdmin={() => setIsAdminOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'discover' ? (
          <div className="space-y-6">
            
            {/* Hero / Header Section */}
            <div className="bg-gradient-to-r from-brand-700 via-brand-800 to-slate-900 rounded-3xl p-6 sm:p-10 text-white shadow-xl relative overflow-hidden">
              <div className="relative z-10 max-w-2xl space-y-3">
                <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md text-brand-100 text-xs font-semibold">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Verified Educational & Career Intelligence</span>
                </div>
                <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">
                  Discover Opportunities Built for Kenyan Students
                </h1>
                <p className="text-xs sm:text-sm text-brand-100/90 leading-relaxed">
                  Search scholarships, industrial attachments, and graduate trainee schemes with verified criteria, deterministic deadline countdowns, and automatic checklist preparation.
                </p>

                {/* Natural Language / Keyword Search Bar */}
                <form onSubmit={handleSearchSubmit} className="pt-2 flex flex-col sm:flex-row gap-2 max-w-xl">
                  <div className="relative flex-1">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search by keywords e.g. Safaricom attachment, HEF loan, Chevening..."
                      className="w-full bg-white text-slate-900 rounded-xl pl-10 pr-4 py-2.5 text-xs font-medium placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-400 shadow-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    className="px-5 py-2.5 bg-brand-500 hover:bg-brand-400 text-white font-semibold text-xs rounded-xl shadow-md transition-colors"
                  >
                    Search
                  </button>
                </form>
              </div>

              {/* Decorative Compass watermark */}
              <div className="absolute right-0 bottom-0 opacity-10 pointer-events-none transform translate-x-10 translate-y-10">
                <Compass className="w-72 h-72 text-white" />
              </div>
            </div>

            {/* Filter Bar */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-1">
              {/* Category Pills */}
              <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 max-w-full">
                {categories.map((cat) => (
                  <button
                    key={cat.value}
                    onClick={() => setSelectedCategory(cat.value)}
                    className={`whitespace-nowrap px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                      selectedCategory === cat.value
                        ? 'bg-brand-600 text-white shadow-sm'
                        : 'bg-white border border-slate-200 text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {cat.label}
                  </button>
                ))}
              </div>

              {/* Open Only Toggle */}
              <div className="flex items-center space-x-2 text-xs font-medium text-slate-700 bg-white px-3 py-1.5 rounded-xl border border-slate-200">
                <input
                  type="checkbox"
                  id="openOnlyToggle"
                  checked={isOpenOnly}
                  onChange={(e) => setIsOpenOnly(e.target.checked)}
                  className="rounded text-brand-600 focus:ring-brand-500"
                />
                <label htmlFor="openOnlyToggle" className="cursor-pointer">
                  Show Open Only
                </label>
              </div>
            </div>

            {/* Opportunities Grid / Loading / Error State */}
            {loading ? (
              <div className="py-20 text-center text-slate-500">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-brand-600 mb-2" />
                <p className="text-sm">Fetching verified opportunities from knowledge base...</p>
              </div>
            ) : error ? (
              <div className="p-6 bg-rose-50 border border-rose-200 rounded-3xl text-center space-y-2">
                <AlertCircle className="w-8 h-8 text-rose-600 mx-auto" />
                <h3 className="font-bold text-sm text-rose-900">API Connection Issue</h3>
                <p className="text-xs text-rose-700 max-w-md mx-auto">{error}</p>
                <button
                  onClick={loadOpportunities}
                  className="px-4 py-2 bg-rose-600 text-white rounded-xl text-xs font-semibold hover:bg-rose-700"
                >
                  Retry Connection
                </button>
              </div>
            ) : opportunities.length === 0 ? (
              <div className="py-20 text-center bg-white rounded-3xl border border-slate-200 p-8 space-y-3">
                <Compass className="w-12 h-12 text-slate-300 mx-auto" />
                <h3 className="font-bold text-base text-slate-800">No opportunities match this filter</h3>
                <p className="text-xs text-slate-500 max-w-md mx-auto">
                  Try adjusting your search keywords or switching category filters to view other verified programs.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {opportunities.map((opp) => (
                  <OpportunityCard
                    key={opp.id}
                    opportunity={opp}
                    onSelect={(item) => setSelectedOpportunity(item)}
                    onCheckEligibility={(item) => setEligibilityOpportunity(item)}
                    onSave={handleSaveToTracker}
                    isTracked={trackedIds.has(opp.id)}
                  />
                ))}
              </div>
            )}

          </div>
        ) : (
          /* Application Tracker Tab */
          <ApplicationTracker
            student={student}
            onOpenAssistant={() => setIsAssistantOpen(true)}
          />
        )}
      </main>

      {/* Floating AI Advisor Trigger Button */}
      <button
        onClick={() => setIsAssistantOpen(true)}
        className="fixed bottom-6 right-6 z-40 p-3.5 bg-gradient-to-r from-brand-600 to-brand-700 hover:from-brand-700 hover:to-brand-800 text-white rounded-full shadow-xl hover:shadow-2xl transition-all flex items-center space-x-2"
        title="Open AI Opportunity Assistant"
      >
        <Bot className="w-5 h-5" />
        <span className="text-xs font-bold pr-1 hidden sm:inline">Ask AI Advisor</span>
      </button>

      {/* Modals & Drawers */}
      <OpportunityModal
        opportunity={selectedOpportunity}
        onClose={() => setSelectedOpportunity(null)}
        onCheckEligibility={(item) => setEligibilityOpportunity(item)}
        onSave={handleSaveToTracker}
        isTracked={selectedOpportunity ? trackedIds.has(selectedOpportunity.id) : false}
      />

      <EligibilityChecker
        opportunity={eligibilityOpportunity}
        student={student}
        onClose={() => setEligibilityOpportunity(null)}
        onSave={handleSaveToTracker}
        isTracked={eligibilityOpportunity ? trackedIds.has(eligibilityOpportunity.id) : false}
      />

      <AIAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        student={student}
      />

      <ProfileModal
        isOpen={isProfileOpen}
        onClose={() => setIsProfileOpen(false)}
        student={student}
        onProfileSaved={(updated) => setStudent(updated)}
        onProfileDeleted={() => {
          setStudent(null);
          setTrackedIds(new Set());
          alert('Profile and tracked application data have been deleted.');
        }}
      />

      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        user={user}
        onAuthSuccess={handleAuthSuccess}
        onLogout={handleLogout}
      />

      <AdminPortalModal
        isOpen={isAdminOpen}
        onClose={() => setIsAdminOpen(false)}
        opportunities={opportunities}
        onOpportunityUpdated={loadOpportunities}
      />

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 mt-12 py-6 text-center text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 space-y-1">
          <p className="font-semibold text-slate-700">
            Opportunity Intelligence AI — University Students Platform (Kenya)
          </p>
          <p className="text-[11px] text-slate-400">
            Official Source Attribution & Anti-Scam Verification • Deterministic Deadline Integrity • RAG Architecture
          </p>
        </div>
      </footer>

    </div>
  );
}
