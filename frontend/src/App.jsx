import React, { useState, useEffect } from 'react';
import { api, getToken, setToken } from './api/client';
import Sidebar from './components/Sidebar';
import TopHeader from './components/TopHeader';
import HomeDashboard from './components/HomeDashboard';
import OpportunityExplorer from './components/OpportunityExplorer';
import AIAdvisorWorkspace from './components/AIAdvisorWorkspace';
import ApplicationPlanner from './components/ApplicationPlanner';
import PersonalizedMatches from './components/PersonalizedMatches';
import OpportunityModal from './components/OpportunityModal';
import EligibilityChecker from './components/EligibilityChecker';
import ProfileModal from './components/ProfileModal';
import AuthModal from './components/AuthModal';
import AdminPortalModal from './components/AdminPortalModal';
import AIAssistantDrawer from './components/AIAssistantDrawer';

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [isOpenOnly, setIsOpenOnly] = useState(false);

  const [user, setUser] = useState(null);
  const [student, setStudent] = useState(null);
  const [trackedIds, setTrackedIds] = useState(new Set());

  const [selectedOpportunity, setSelectedOpportunity] = useState(null);
  const [eligibilityOpportunity, setEligibilityOpportunity] = useState(null);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [isAdminOpen, setIsAdminOpen] = useState(false);

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

  const handleGlobalSearch = (e) => {
    if (e) e.preventDefault();
    setActiveTab('explore');
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

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex font-['Inter',sans-serif] text-slate-800">
      
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenProfile={() => (user ? setIsProfileOpen(true) : setIsAuthOpen(true))}
        onOpenAdmin={() => setIsAdminOpen(true)}
        onOpenAssistantDrawer={() => setIsAssistantOpen(true)}
      />

      <div className="flex-1 flex flex-col min-w-0 min-h-screen">
        
        <TopHeader
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          onSearch={handleGlobalSearch}
          user={user}
          onOpenAuth={() => setIsAuthOpen(true)}
          onOpenProfile={() => (user ? setIsProfileOpen(true) : setIsAuthOpen(true))}
          onOpenAdmin={() => setIsAdminOpen(true)}
        />

        <main className="flex-1 p-6 sm:p-8 max-w-7xl w-full mx-auto">
          
          {activeTab === 'dashboard' && (
            <HomeDashboard
              opportunities={opportunities}
              onSelectOpportunity={(opp) => setSelectedOpportunity(opp)}
              onCheckEligibility={(opp) => setEligibilityOpportunity(opp)}
              onNavigateToExplore={() => setActiveTab('explore')}
              onNavigateToAI={() => setActiveTab('ai-workspace')}
              onNavigateToMatches={() => setActiveTab('matches')}
              onNavigateToPlanner={() => setActiveTab('planner')}
            />
          )}

          {activeTab === 'matches' && (
            <PersonalizedMatches
              user={user}
              student={student}
              onOpenAuth={() => setIsAuthOpen(true)}
              onOpenProfile={() => (user ? setIsProfileOpen(true) : setIsAuthOpen(true))}
              onSelectOpportunity={(opp) => setSelectedOpportunity(opp)}
              onCheckEligibility={(opp) => setEligibilityOpportunity(opp)}
            />
          )}

          {(activeTab === 'planner' || activeTab === 'tracker') && (
            <ApplicationPlanner
              student={student}
              onOpenAssistant={() => setActiveTab('ai-workspace')}
              onOpenExplore={() => setActiveTab('explore')}
              onSelectOpportunity={(opp) => setSelectedOpportunity(opp)}
            />
          )}

          {activeTab === 'explore' && (
            <OpportunityExplorer
              opportunities={opportunities}
              loading={loading}
              error={error}
              searchQuery={searchQuery}
              setSearchQuery={setSearchQuery}
              selectedCategory={selectedCategory}
              setSelectedCategory={setSelectedCategory}
              isOpenOnly={isOpenOnly}
              setIsOpenOnly={setIsOpenOnly}
              onSelectOpportunity={(opp) => setSelectedOpportunity(opp)}
              onCheckEligibility={(opp) => setEligibilityOpportunity(opp)}
              onSaveToTracker={handleSaveToTracker}
              trackedIds={trackedIds}
            />
          )}

          {activeTab === 'ai-workspace' && (
            <AIAdvisorWorkspace
              student={student}
              user={user}
            />
          )}

          {activeTab === 'eligibility' && (
            <div className="bg-white rounded-3xl p-8 border border-slate-200/80 space-y-6">
              <div>
                <h3 className="text-xl font-extrabold text-slate-900">Deterministic Eligibility Evaluator</h3>
                <p className="text-xs text-slate-500">
                  Select an opportunity below or browse the directory to test your academic criteria with zero language model hallucination.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {opportunities.map((opp) => (
                  <div
                    key={opp.id}
                    className="p-4 rounded-2xl border border-slate-200 hover:border-brand-400 hover:bg-brand-50/20 transition-all flex flex-col justify-between"
                  >
                    <div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700">
                        {opp.category}
                      </span>
                      <h4 className="font-bold text-xs text-slate-900 mt-2 line-clamp-2">{opp.title}</h4>
                      <p className="text-[11px] text-slate-500 mt-0.5">{opp.provider}</p>
                    </div>
                    <button
                      onClick={() => setEligibilityOpportunity(opp)}
                      className="mt-4 w-full py-1.5 px-3 bg-brand-600 hover:bg-brand-700 text-white font-semibold text-xs rounded-xl transition-colors"
                    >
                      Assess My Eligibility
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

        </main>

        <footer className="border-t border-slate-200/80 bg-white py-4 px-8 text-center text-xs text-slate-400">
          <p className="font-semibold text-slate-600">Opportunity Intelligence AI — Kenyan University Students Platform</p>
          <p className="text-[11px] text-slate-400 mt-0.5">
            Strict Source Attribution • Anti-Scam Verification • Deterministic Deadline Integrity • Agentic RAG
          </p>
        </footer>

      </div>

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

    </div>
  );
}
