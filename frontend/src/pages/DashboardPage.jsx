import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getHistory } from '../services/api';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';

export default function DashboardPage() {
    const navigate = useNavigate();
    const [history, setHistory] = useState([]);
    const [loading, setLoading] = useState(true);
    const user = JSON.parse(localStorage.getItem('user') || '{}');

    useEffect(() => {
        const load = async () => {
            try {
                const res = await getHistory();
                setHistory(res.data);
            } catch {
                // If unauthorized, redirect to login
                navigate('/login');
            } finally {
                setLoading(false);
            }
        };
        load();
    }, []);

    const completedSessions = history.filter((s) => s.status === 'completed');
    const avgScore = completedSessions.length
        ? Math.round(completedSessions.reduce((sum, s) => sum + (s.overall_score || 0), 0) / completedSessions.length)
        : 0;
    const bestScore = completedSessions.length
        ? Math.round(Math.max(...completedSessions.map((s) => s.overall_score || 0)))
        : 0;

    const chartData = completedSessions.slice(0, 10).reverse().map((s, i) => ({
        name: `#${i + 1}`,
        score: Math.round(s.overall_score || 0),
        type: s.interview_type,
    }));

    if (loading) {
        return (
            <div className="loading-page">
                <div className="spinner" />
                <p>Loading dashboard...</p>
            </div>
        );
    }

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Welcome back, {user.name || 'User'}</h1>
                <p className="page-subtitle">Track your progress and continue practicing</p>
            </div>

            {/* Stats */}
            <div className="stats-grid">
                <div className="card stat-card">
                    <div className="stat-value">{history.length}</div>
                    <div className="stat-label">Total Sessions</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value">{completedSessions.length}</div>
                    <div className="stat-label">Completed</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value">{avgScore}%</div>
                    <div className="stat-label">Average Score</div>
                </div>
                <div className="card stat-card">
                    <div className="stat-value">{bestScore}%</div>
                    <div className="stat-label">Best Score</div>
                </div>
            </div>

            <div className="grid-2" style={{ marginBottom: '2rem' }}>
                {/* Quick Start */}
                <div className="card">
                    <div className="card-header">
                        <div className="card-title">Quick Start</div>
                        <div className="card-subtitle">Begin a new mock interview</div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                        <Link to="/interview/hr" className="btn btn-secondary">👔 HR Interview</Link>
                        <Link to="/interview/technical" className="btn btn-secondary">💻 Technical</Link>
                        <Link to="/interview/exam" className="btn btn-secondary">📝 Exam / Viva</Link>
                    </div>
                    <div style={{ marginTop: '1rem' }}>
                        <Link to="/select" className="btn btn-primary">Choose Interview Type →</Link>
                    </div>
                </div>

                {/* Score Trend */}
                <div className="card">
                    <div className="card-header">
                        <div className="card-title">Score Trend</div>
                        <div className="card-subtitle">Your recent session scores</div>
                    </div>
                    {chartData.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                            <BarChart data={chartData}>
                                <CartesianGrid stroke="rgba(255,255,255,0.05)" />
                                <XAxis dataKey="name" tick={{ fill: '#64748b', fontSize: 12 }} />
                                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{
                                        background: '#1e293b',
                                        border: '1px solid rgba(255,255,255,0.1)',
                                        borderRadius: '8px',
                                        color: '#f1f5f9',
                                    }}
                                />
                                <Bar dataKey="score" fill="#818cf8" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    ) : (
                        <div className="empty-state">
                            <div className="empty-state-desc">Complete interviews to see your score trend</div>
                        </div>
                    )}
                </div>
            </div>

            {/* Session History */}
            <div className="card">
                <div className="card-header">
                    <div className="card-title">Interview History</div>
                </div>
                {history.length > 0 ? (
                    <table className="history-table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Status</th>
                                <th>Questions</th>
                                <th>Score</th>
                                <th>Date</th>
                                <th></th>
                            </tr>
                        </thead>
                        <tbody>
                            {history.map((s) => (
                                <tr key={s.id}>
                                    <td>
                                        <span className={`badge badge-${s.interview_type}`}>
                                            {s.interview_type.toUpperCase()}
                                        </span>
                                    </td>
                                    <td style={{ color: s.status === 'completed' ? 'var(--success)' : 'var(--warning)' }}>
                                        {s.status}
                                    </td>
                                    <td>{s.total_questions}</td>
                                    <td style={{ fontWeight: 700 }}>
                                        {s.overall_score != null ? `${Math.round(s.overall_score)}%` : '—'}
                                    </td>
                                    <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                                        {new Date(s.start_time).toLocaleDateString()}
                                    </td>
                                    <td>
                                        {s.status === 'completed' && (
                                            <Link to={`/report/${s.id}`} className="btn btn-sm btn-secondary">
                                                View Report
                                            </Link>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                ) : (
                    <div className="empty-state">
                        <div className="empty-state-icon">🎯</div>
                        <div className="empty-state-title">No interviews yet</div>
                        <div className="empty-state-desc">Start your first mock interview to begin tracking your progress</div>
                        <Link to="/select" className="btn btn-primary" style={{ marginTop: '1rem' }}>
                            Start Interview
                        </Link>
                    </div>
                )}
            </div>
        </div>
    );
}
