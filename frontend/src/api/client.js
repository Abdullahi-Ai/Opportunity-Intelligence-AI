
const BASE_URL = '/api/v1';
const TOKEN_KEY = 'oi_access_token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
};

async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  const token = getToken();

  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
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
  login: (email, password) => {
    return request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  register: (userData) => {
    return request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  },

  getMe: () => request('/auth/me'),

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

  chat: (message, conversationIdOrSession = null, sessionId = null, studentId = null) => {
    let conversationId = null;
    let actualSessionId = sessionId;
    let actualStudentId = studentId;

    if (conversationIdOrSession) {
      if (
        conversationIdOrSession.startsWith('conv-') || 
        (conversationIdOrSession.includes('-') && conversationIdOrSession.length >= 32)
      ) {
        conversationId = conversationIdOrSession;
      } else if (!sessionId) {
        actualSessionId = conversationIdOrSession;
      } else {
        conversationId = conversationIdOrSession;
      }
    }

    return request('/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        conversation_id: conversationId,
        session_id: actualSessionId || 'default_session',
        student_id: actualStudentId,
      }),
    });
  },

  getConversations: (sessionId = null) => {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return request(`/conversations${q}`);
  },

  getConversationHistory: (conversationId, sessionId = null) => {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return request(`/conversations/${encodeURIComponent(conversationId)}${q}`);
  },

  renameConversation: (conversationId, title, sessionId = null) => {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return request(`/conversations/${encodeURIComponent(conversationId)}${q}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    });
  },

  deleteConversation: (conversationId, sessionId = null) => {
    const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : '';
    return request(`/conversations/${encodeURIComponent(conversationId)}${q}`, {
      method: 'DELETE',
    });
  },

  assessEligibility: (data) => {
    return request('/agent/assess-eligibility', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

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

  adminCreateOpportunity: (data) => {
    return request('/admin/opportunities', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  adminUpdateOpportunity: (id, data) => {
    return request(`/admin/opportunities/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  adminVerifyOpportunity: (id, verificationData) => {
    return request(`/admin/opportunities/${id}/verify`, {
      method: 'POST',
      body: JSON.stringify(verificationData),
    });
  },

  adminDeleteOpportunity: (id) => {
    return request(`/admin/opportunities/${id}`, {
      method: 'DELETE',
    });
  },
};
