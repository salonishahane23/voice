import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Add JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth APIs
export const register = (name, email, password) =>
  api.post('/auth/register', { name, email, password });

export const login = (email, password) =>
  api.post('/auth/login', { email, password });

export const getMe = () => api.get('/auth/me');

// Interview APIs
export const startInterview = (interviewType, totalQuestions = 5) =>
  api.post('/interviews/start', { interview_type: interviewType, total_questions: totalQuestions });

export const submitResponse = (sessionId, formData) =>
  api.post(`/interviews/${sessionId}/respond`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

export const getNextQuestion = (sessionId) =>
  api.get(`/interviews/${sessionId}/next`);

export const endInterview = (sessionId) =>
  api.post(`/interviews/${sessionId}/end`);

export const getReport = (sessionId) =>
  api.get(`/interviews/${sessionId}/report`);

export const getHistory = () => api.get('/interviews/history');

// Question APIs
export const getCategories = () => api.get('/questions/categories');

// DSA APIs
export const startDSA = (numQuestions = 3, difficulty = null) =>
  api.post('/dsa/start', { num_questions: numQuestions, difficulty_preference: difficulty });

export const getDSAQuestion = (sessionId) =>
  api.get(`/dsa/${sessionId}/question`);

export const submitDSAApproach = (sessionId, questionId, approachText) =>
  api.post(`/dsa/${sessionId}/submit`, { question_id: questionId, approach_text: approachText });

export const getNextDSAQuestion = (sessionId) =>
  api.get(`/dsa/${sessionId}/next`);

export const endDSA = (sessionId) =>
  api.post(`/dsa/${sessionId}/end`);

export const getDSAReport = (sessionId) =>
  api.get(`/dsa/${sessionId}/report`);

export default api;
