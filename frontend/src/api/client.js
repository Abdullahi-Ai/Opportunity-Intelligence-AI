/**
 * Opportunity Intelligence AI - Frontend API Client
 * Connects React UI to FastAPI backend endpoints.
 */

const BASE_URL = '/api/v1';

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed with status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`API Error on ${endpoint}:`, error);
    throw error;
  }
}

export const api = {
  // 1. Opportunities Discovery
  getOpportunities: (params = {}) => {
    const query = new URLSearchParams();
    if (params.category) query.append('category', params.category);
    if (params.degree_level) query.append('degree_level', params.degree_level);
    if (params.search) query.append('search', params.search);
    if (params.is_open_only) query.append('is_open_only', 'true');
    const queryString = query.toString() ? `?${query.toString()}` : '';
    return request(`/opportunities${queryString}`);
  },

  getOpportunityDetails: (id) => request(`/opportunities/${id}`),

  // 2. AI Assistant Chat
  chat: (message, sessionId = 'default_session', studentId = null) => {
    return request('/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        session_id: sessionId,
        student_id: studentId,
      }),
    });
  },

  // 3. Deterministic Eligibility Checker
  assessEligibility: (data) => {
    return request('/agent/assess-eligibility', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  // 4. Student Profile Management
  getProfile: (email) => request(`/profile/${encodeURIComponent(email)}`),
  saveProfile: (profileData) => {
    return request('/profile', {
      method: 'POST',
      body: JSON.stringify(profileData),
    });
  },
  deleteProfile: (email) => {
    return request(`/profile/${encodeURIComponent(email)}`, {
      method: 'DELETE',
    });
  },

  // 5. Application Tracking & Checklists
  saveToTracker: (studentId, opportunityId, stage = 'Saved', notes = '') => {
    return request('/tracker/save', {
      method: 'POST',
      body: JSON.stringify({
        student_id: studentId,
        opportunity_id: opportunityId,
        stage,
        notes,
        auto_generate_checklist: true,
      }),
    });
  },

  getTrackedApplications: (studentId) => request(`/tracker/${studentId}`),

  updateApplicationStage: (trackedAppId, newStage) => {
    return request(`/tracker/${trackedAppId}/stage?new_stage=${encodeURIComponent(newStage)}`, {
      method: 'PATCH',
    });
  },

  removeTrackedApplication: (studentId, opportunityId) => {
    return request(`/tracker/${studentId}/${opportunityId}`, {
      method: 'DELETE',
    });
  },

  toggleChecklistTask: (checklistId) => {
    return request(`/checklists/${checklistId}/toggle`, {
      method: 'PATCH',
    });
  },

  addCustomChecklistTask: (trackedAppId, taskDescription, docType = 'Custom') => {
    return request(`/tracker/${trackedAppId}/checklists`, {
      method: 'POST',
      body: JSON.stringify({
        task_description: taskDescription,
        required_document_type: docType,
      }),
    });
  },

  deleteChecklistTask: (checklistId) => {
    return request(`/checklists/${checklistId}`, {
      method: 'DELETE',
    });
  },

  getDashboardStats: (studentId) => request(`/tracker/${studentId}/stats`),
};
