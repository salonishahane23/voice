import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { startDSA, submitDSAApproach, getNextDSAQuestion, endDSA } from '../services/api';

function ScoreRing({ score, label, size = 80 }) {
    const radius = (size - 8) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;
    const color = score >= 70 ? '#34d399' : score >= 45 ? '#fbbf24' : '#f87171';

    return (
        <div className="dsa-score-ring-wrapper">
            <svg width={size} height={size} className="dsa-score-ring-svg">
                <circle cx={size / 2} cy={size / 2} r={radius} strokeWidth="6" fill="none" stroke="rgba(255,255,255,0.08)" />
                <circle
                    cx={size / 2} cy={size / 2} r={radius} strokeWidth="6" fill="none"
                    stroke={color}
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    strokeLinecap="round"
                    style={{ transition: 'stroke-dashoffset 1s ease', transform: 'rotate(-90deg)', transformOrigin: 'center' }}
                />
                <text x="50%" y="50%" textAnchor="middle" dy="0.35em" fill={color} fontSize="16" fontWeight="700">
                    {Math.round(score)}
                </text>
            </svg>
            <div className="dsa-score-ring-label">{label}</div>
        </div>
    );
}

function DifficultyBadge({ difficulty }) {
    const cls = difficulty === 'easy' ? 'badge-easy' : difficulty === 'hard' ? 'badge-hard' : 'badge-medium';
    return <span className={`difficulty-badge ${cls}`}>{difficulty}</span>;
}

function TopicTag({ topic }) {
    return <span className="topic-tag">{topic}</span>;
}

export default function DSASessionPage() {
    const navigate = useNavigate();

    const [session, setSession] = useState(null);
    const [question, setQuestion] = useState(null);
    const [loading, setLoading] = useState(true);
    const [approach, setApproach] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [evaluation, setEvaluation] = useState(null);
    const [error, setError] = useState('');
    const [timer, setTimer] = useState(0);
    const [finished, setFinished] = useState(false);

    const timerRef = useRef(null);

    // Start DSA session
    useEffect(() => {
        const init = async () => {
            try {
                const res = await startDSA(3);
                setSession(res.data.session);
                setQuestion(res.data.question);
            } catch (err) {
                const msg = err.response?.data?.detail || 'Failed to start DSA session';
                setError(msg);
            } finally {
                setLoading(false);
            }
        };
        init();
        return () => { if (timerRef.current) clearInterval(timerRef.current); };
    }, []);

    // Timer
    useEffect(() => {
        if (session && question && !evaluation && !finished) {
            setTimer(0);
            timerRef.current = setInterval(() => setTimer(t => t + 1), 1000);
            return () => clearInterval(timerRef.current);
        }
    }, [question?.id, evaluation, finished]);

    const formatTime = (s) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
    };

    const handleSubmit = async () => {
        if (!approach.trim()) { setError('Please write your approach before submitting.'); return; }
        setSubmitting(true);
        setError('');
        try {
            const res = await submitDSAApproach(session.id, question.id, approach);
            setEvaluation(res.data);
            if (timerRef.current) clearInterval(timerRef.current);
        } catch (err) {
            const msg = err.response?.data?.detail || 'Failed to evaluate approach';
            setError(msg);
        } finally {
            setSubmitting(false);
        }
    };

    const handleNext = async () => {
        setEvaluation(null);
        setApproach('');
        setError('');
        try {
            const res = await getNextDSAQuestion(session.id);
            if (res.data.status === 'completed') {
                await endDSA(session.id);
                setFinished(true);
                navigate(`/report/${session.id}`);
            } else {
                setQuestion(res.data.question);
            }
        } catch {
            setError('Failed to get next question');
        }
    };

    const handleEnd = async () => {
        try {
            await endDSA(session.id);
            setFinished(true);
            navigate(`/report/${session.id}`);
        } catch {
            setError('Failed to end session');
        }
    };

    if (loading) {
        return (
            <div className="loading-page">
                <div className="spinner" />
                <p>Generating DSA problems...</p>
                <p className="loading-sub">This may take a few seconds</p>
            </div>
        );
    }

    if (error && !session) {
        return (
            <div className="page">
                <div className="alert alert-error">{error}</div>
                <button className="btn btn-secondary" onClick={() => navigate('/select')}>Go Back</button>
            </div>
        );
    }

    return (
        <div className="page">
            <div className="dsa-container">
                {/* Progress */}
                {question && (
                    <div className="session-progress">
                        <div className="progress-bar-bg">
                            <div
                                className="progress-bar-fill"
                                style={{ width: `${((question.question_order + 1) / question.total_questions) * 100}%` }}
                            />
                        </div>
                        <span className="progress-text">
                            {question.question_order + 1} / {question.total_questions}
                        </span>
                    </div>
                )}

                {error && <div className="alert alert-error">{error}</div>}

                {/* Problem Card */}
                <div className="card dsa-problem-card">
                    <div className="dsa-problem-header">
                        <div className="dsa-problem-title-row">
                            <h2 className="dsa-problem-title">{question?.title}</h2>
                            <div className="dsa-problem-meta">
                                <DifficultyBadge difficulty={question?.difficulty} />
                                <TopicTag topic={question?.topic} />
                            </div>
                        </div>
                        <div className="dsa-timer">
                            <span className="dsa-timer-icon">⏱</span>
                            <span>{formatTime(timer)}</span>
                        </div>
                    </div>

                    <div className="dsa-problem-body">
                        <pre className="dsa-problem-description">{question?.description}</pre>
                    </div>

                    {question?.hints && (
                        <div className="dsa-hint">
                            <span className="dsa-hint-icon">💡</span>
                            <span>{question.hints}</span>
                        </div>
                    )}
                </div>

                {/* Approach Editor */}
                {!evaluation && (
                    <div className="card dsa-approach-card">
                        <h3 className="dsa-section-title">Your Approach & Pseudocode</h3>
                        <p className="dsa-section-sub">
                            Describe your thought process, algorithm, and pseudocode. You do NOT need to write actual code.
                        </p>
                        <textarea
                            className="dsa-approach-editor"
                            value={approach}
                            onChange={(e) => setApproach(e.target.value)}
                            placeholder={`Describe your approach here...\n\nFor example:\n1. First, I would...\n2. Then, iterate through...\n\nPseudocode:\nfunction solve(arr):\n    create a hashmap\n    for each element in arr:\n        if complement exists in hashmap:\n            return indices\n        add element to hashmap\n\nTime complexity: O(n)\nSpace complexity: O(n)\n\nEdge cases:\n- Empty array\n- Single element\n- No valid pair`}
                            rows={16}
                            disabled={submitting}
                        />
                        <div className="dsa-approach-actions">
                            <button
                                className="btn btn-primary dsa-submit-btn"
                                onClick={handleSubmit}
                                disabled={submitting || !approach.trim()}
                            >
                                {submitting ? (
                                    <>
                                        <div className="spinner-sm" />
                                        Evaluating...
                                    </>
                                ) : (
                                    '🚀 Submit Approach'
                                )}
                            </button>
                            {!evaluation && (
                                <button className="btn btn-secondary btn-sm" onClick={handleEnd}>
                                    Skip & End
                                </button>
                            )}
                        </div>
                    </div>
                )}

                {/* Evaluation Results */}
                {evaluation && (
                    <div className="card dsa-evaluation-card">
                        <h3 className="dsa-section-title">Evaluation Results</h3>

                        {/* Overall Score */}
                        <div className="dsa-overall-score-section">
                            <ScoreRing score={evaluation.overall_score} label="Overall" size={120} />
                        </div>

                        {/* Individual Scores */}
                        <div className="dsa-scores-grid">
                            <ScoreRing score={evaluation.score_correctness} label="Correctness" />
                            <ScoreRing score={evaluation.score_time_complexity} label="Time Complexity" />
                            <ScoreRing score={evaluation.score_space_complexity} label="Space Complexity" />
                            <ScoreRing score={evaluation.score_edge_cases} label="Edge Cases" />
                            <ScoreRing score={evaluation.score_clarity} label="Clarity" />
                        </div>

                        {/* Complexity Analysis */}
                        {evaluation.time_complexity_analysis && (
                            <div className="dsa-complexity-analysis">
                                <span className="dsa-complexity-label">Complexity Analysis:</span>
                                <span className="dsa-complexity-value">{evaluation.time_complexity_analysis}</span>
                            </div>
                        )}

                        {/* Feedback */}
                        {evaluation.feedback && (
                            <div className="dsa-feedback-panel">
                                <h4>📝 Feedback</h4>
                                <p>{evaluation.feedback}</p>
                            </div>
                        )}

                        {/* Optimal Approach */}
                        {evaluation.optimal_approach && (
                            <div className="dsa-optimal-panel">
                                <h4>✨ Optimal Approach</h4>
                                <p>{evaluation.optimal_approach}</p>
                            </div>
                        )}

                        {/* Navigation */}
                        <div className="dsa-nav-actions">
                            <button className="btn btn-primary" onClick={handleNext}>
                                {question.question_order + 1 < question.total_questions ? 'Next Question →' : 'Finish & View Report'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
