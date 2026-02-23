import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { getReport, getDSAReport } from '../services/api';
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer } from 'recharts';

/* ── helper: format seconds → "0:32" ── */
function fmtTime(s) {
    if (s == null) return '—';
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${sec.toString().padStart(2, '0')}`;
}

/* ── helper: score → css class ── */
function scoreClass(pct) {
    if (pct >= 75) return 'excellent';
    if (pct >= 55) return 'good';
    if (pct >= 35) return 'average';
    return 'poor';
}

/* ── helper: score → color variable ── */
function scoreColor(pct) {
    if (pct >= 75) return 'var(--success)';
    if (pct >= 55) return 'var(--info)';
    if (pct >= 35) return 'var(--warning)';
    return 'var(--error)';
}

/* ── Metric Bar component ── */
function MetricBar({ label, value, max = 1, suffix = '', color }) {
    const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
    const barColor = color || scoreColor(pct);
    return (
        <div className="da-metric">
            <div className="da-metric-header">
                <span className="da-metric-label">{label}</span>
                <span className="da-metric-value" style={{ color: barColor }}>
                    {typeof value === 'number' ? (Number.isInteger(value) ? value : value.toFixed(2)) : value}{suffix}
                </span>
            </div>
            <div className="da-bar-track">
                <div className="da-bar-fill" style={{ width: `${pct}%`, background: barColor }} />
            </div>
        </div>
    );
}

/* ── Stat Pill component ── */
function StatPill({ icon, label, value, color }) {
    return (
        <div className="da-stat-pill">
            <span className="da-stat-icon">{icon}</span>
            <span className="da-stat-label">{label}</span>
            <span className="da-stat-value" style={{ color: color || 'var(--text-primary)' }}>{value}</span>
        </div>
    );
}

/* ───────────────────────────────────────────────────
   VOICE DEEP ANALYSIS SECTION
   ─────────────────────────────────────────────────── */
function VoiceDeepAnalysis({ voice }) {
    if (!voice) return null;

    const fillers = voice.filler_words || {};
    const fillerInstances = fillers.instances || [];
    const reps = voice.repetitions || {};
    const repInstances = reps.instances || [];
    const rate = voice.speaking_rate || {};
    const pauses = voice.pauses || {};
    const audio = voice.audio_features || {};

    // aggregate filler words by type
    const fillerCounts = {};
    fillerInstances.forEach(f => {
        fillerCounts[f.word] = (fillerCounts[f.word] || 0) + 1;
    });
    const fillerSorted = Object.entries(fillerCounts).sort((a, b) => b[1] - a[1]);

    // figure out when fillers were used most (split into thirds: beginning/middle/end)
    const totalDuration = rate.total_duration || 1;
    const thirdDur = totalDuration / 3;
    let buckets = [0, 0, 0]; // beginning, middle, end
    fillerInstances.forEach(f => {
        const t = f.start || 0;
        if (t < thirdDur) buckets[0]++;
        else if (t < thirdDur * 2) buckets[1]++;
        else buckets[2]++;
    });
    const bucketLabels = ['Beginning', 'Middle', 'End'];
    const maxBucket = Math.max(...buckets);
    const peakSection = buckets.indexOf(maxBucket);

    return (
        <div className="da-section">
            <div className="da-section-title">
                <span className="da-section-icon">🎙️</span> Voice Deep Analysis
            </div>

            {/* Score overview */}
            <div className="da-scores-row">
                <MetricBar label="Fluency" value={voice.fluency_score || 0} suffix="" />
                <MetricBar label="Clarity" value={voice.clarity_score || 0} suffix="" />
                <MetricBar label="Confidence" value={voice.voice_confidence_score || 0} suffix="" />
            </div>

            {/* Speaking Rate */}
            <div className="da-subsection">
                <div className="da-subsection-title">Speaking Rate</div>
                <div className="da-stats-row">
                    <StatPill icon="📊" label="Words/min" value={rate.words_per_minute || 0} color={rate.rating === 'ideal' ? 'var(--success)' : rate.rating === 'too_fast' || rate.rating === 'too_slow' ? 'var(--error)' : 'var(--warning)'} />
                    <StatPill icon="📝" label="Total words" value={rate.total_words || 0} />
                    <StatPill icon="⏱️" label="Duration" value={fmtTime(rate.total_duration)} />
                    <StatPill icon="🏷️" label="Pace" value={(rate.rating || 'unknown').replace(/_/g, ' ')} color={rate.rating === 'ideal' ? 'var(--success)' : 'var(--warning)'} />
                </div>
            </div>

            {/* Filler Words */}
            <div className="da-subsection">
                <div className="da-subsection-title">
                    Filler Words
                    <span className="da-count-badge" style={{ background: fillerInstances.length > 3 ? 'rgba(248,113,113,0.15)' : 'rgba(52,211,153,0.15)', color: fillerInstances.length > 3 ? 'var(--error)' : 'var(--success)' }}>
                        {fillerInstances.length} detected
                    </span>
                </div>

                {fillerSorted.length > 0 ? (
                    <>
                        {/* Frequency breakdown */}
                        <div className="da-filler-freq">
                            {fillerSorted.map(([word, count]) => (
                                <div key={word} className="da-filler-tag">
                                    <span className="da-filler-word">"{word}"</span>
                                    <span className="da-filler-count">×{count}</span>
                                </div>
                            ))}
                        </div>

                        {/* When used most */}
                        {fillerInstances.length >= 2 && (
                            <div className="da-when-most">
                                <div className="da-when-label">Most fillers used: <strong style={{ color: 'var(--warning)' }}>{bucketLabels[peakSection]}</strong> of your answer ({buckets[peakSection]} of {fillerInstances.length})</div>
                                <div className="da-when-bars">
                                    {buckets.map((count, i) => (
                                        <div key={i} className="da-when-bar-item">
                                            <div className="da-when-bar-label">{bucketLabels[i]}</div>
                                            <div className="da-bar-track" style={{ height: '6px' }}>
                                                <div className="da-bar-fill" style={{ width: `${fillerInstances.length > 0 ? (count / fillerInstances.length) * 100 : 0}%`, background: i === peakSection ? 'var(--warning)' : 'var(--text-muted)' }} />
                                            </div>
                                            <div className="da-when-bar-count">{count}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Timeline */}
                        <div className="da-timeline">
                            {fillerInstances.map((f, i) => (
                                <div key={i} className="da-timeline-item">
                                    <span className="da-timeline-time">{fmtTime(f.start)}</span>
                                    <span className="da-timeline-dot filler" />
                                    <div className="da-timeline-content">
                                        <span className="da-timeline-word">"{f.word}"</span>
                                        {f.segment_text && <span className="da-timeline-context">…{f.segment_text.slice(0, 80)}</span>}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </>
                ) : (
                    <div className="da-empty-note">✨ No filler words detected — great job!</div>
                )}
            </div>

            {/* Repetitions */}
            <div className="da-subsection">
                <div className="da-subsection-title">
                    Word Repetitions
                    <span className="da-count-badge" style={{ background: repInstances.length > 2 ? 'rgba(248,113,113,0.15)' : 'rgba(52,211,153,0.15)', color: repInstances.length > 2 ? 'var(--error)' : 'var(--success)' }}>
                        {repInstances.length} detected
                    </span>
                </div>
                {repInstances.length > 0 ? (
                    <div className="da-timeline">
                        {repInstances.map((r, i) => (
                            <div key={i} className="da-timeline-item">
                                <span className="da-timeline-time">{fmtTime(r.start)}</span>
                                <span className="da-timeline-dot repetition" />
                                <div className="da-timeline-content">
                                    <span className="da-timeline-word">"{r.word}" repeated</span>
                                    {r.segment_text && <span className="da-timeline-context">…{r.segment_text.slice(0, 80)}</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="da-empty-note">✨ No repetitions detected — smooth delivery!</div>
                )}
            </div>

            {/* Pauses */}
            <div className="da-subsection">
                <div className="da-subsection-title">Pauses</div>
                <div className="da-stats-row">
                    <StatPill icon="⏸️" label="Avg pause" value={`${(pauses.avg_pause || 0).toFixed(2)}s`} />
                    <StatPill icon="⏱️" label="Max pause" value={`${(pauses.max_pause || 0).toFixed(2)}s`} />
                    <StatPill icon="😬" label="Awkward silences" value={pauses.awkward_silence_count || 0} color={(pauses.awkward_silence_count || 0) > 0 ? 'var(--warning)' : 'var(--success)'} />
                </div>
                {(pauses.long_pauses || []).length > 0 && (
                    <div className="da-timeline" style={{ marginTop: '0.75rem' }}>
                        {pauses.long_pauses.map((p, i) => (
                            <div key={i} className="da-timeline-item">
                                <span className="da-timeline-time">{fmtTime(p.start)}</span>
                                <span className="da-timeline-dot pause" />
                                <div className="da-timeline-content">
                                    <span className="da-timeline-word">{p.duration}s silence</span>
                                    {p.after_text && <span className="da-timeline-context">after "…{p.after_text}"</span>}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Audio Features */}
            <div className="da-subsection">
                <div className="da-subsection-title">Audio Quality</div>
                <div className="da-scores-row">
                    <MetricBar label="Volume Consistency" value={audio.volume_consistency || 0} />
                    <MetricBar label="Pitch Variation" value={Math.min((audio.pitch_std || 0) / 80, 1)} color={(audio.pitch_std || 0) < 10 ? 'var(--warning)' : 'var(--success)'} />
                </div>
            </div>
        </div>
    );
}

/* ───────────────────────────────────────────────────
   VIDEO / FACIAL DEEP ANALYSIS SECTION
   ─────────────────────────────────────────────────── */
function VideoDeepAnalysis({ facial }) {
    const [expandedFrame, setExpandedFrame] = useState(null);
    if (!facial) return null;

    const posture = facial.posture || {};
    const postureFrames = facial.posture_frames || [];
    const eyeContact = facial.eye_contact || {};
    const emotions = facial.emotions || {};
    const emotionDist = emotions.emotion_distribution || {};
    const emotionEntries = Object.entries(emotionDist).sort((a, b) => b[1] - a[1]);
    const totalEmotionFrames = emotionEntries.reduce((sum, e) => sum + e[1], 0);

    return (
        <div className="da-section">
            <div className="da-section-title">
                <span className="da-section-icon">📹</span> Video Deep Analysis
            </div>

            {/* Overall scores */}
            <div className="da-scores-row">
                <MetricBar label="Confidence" value={facial.face_confidence_score || 0} />
                <MetricBar label="Engagement" value={facial.face_engagement_score || 0} />
            </div>

            <div className="da-stats-row" style={{ marginTop: '0.5rem' }}>
                <StatPill icon="🎥" label="Frames analyzed" value={facial.frames_analyzed || 0} />
                <StatPill icon="👤" label="Face detected" value={`${facial.frames_with_face || 0} frames`} />
                <StatPill icon="🦴" label="Shoulders detected" value={`${facial.frames_with_shoulders || 0} frames`} />
                <StatPill icon="⚙️" label="Method" value={facial.analysis_method || '—'} />
            </div>

            {/* Posture / Slouch Analysis */}
            <div className="da-subsection">
                <div className="da-subsection-title">
                    Posture & Slouch Detection
                    {posture.shoulder_slouch_detected || posture.slouching_detected ? (
                        <span className="da-count-badge" style={{ background: 'rgba(248,113,113,0.15)', color: 'var(--error)' }}>⚠ Slouching detected</span>
                    ) : (
                        <span className="da-count-badge" style={{ background: 'rgba(52,211,153,0.15)', color: 'var(--success)' }}>✓ Good posture</span>
                    )}
                </div>

                <MetricBar label="Posture Score" value={posture.posture_score || 0} />

                <div className="da-detail-grid">
                    {posture.shoulder_slope != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Shoulder Slope (tilt)</span>
                            <span className="da-detail-value" style={{ color: (posture.shoulder_slope || 0) > 0.15 ? 'var(--warning)' : 'var(--success)' }}>
                                {posture.shoulder_slope.toFixed(4)}
                            </span>
                            <span className="da-detail-note">{(posture.shoulder_slope || 0) > 0.15 ? 'Significant shoulder tilt' : 'Level shoulders'}</span>
                        </div>
                    )}
                    {posture.shoulder_y_drift != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Vertical Drift (slouch)</span>
                            <span className="da-detail-value" style={{ color: (posture.shoulder_y_drift || 0) > 0.03 ? 'var(--error)' : 'var(--success)' }}>
                                {posture.shoulder_y_drift.toFixed(4)}
                            </span>
                            <span className="da-detail-note">{(posture.shoulder_y_drift || 0) > 0.03 ? 'Shoulders dropped over time' : 'Maintained shoulder height'}</span>
                        </div>
                    )}
                    {posture.shoulder_spread_change != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Spread Change (hunching)</span>
                            <span className="da-detail-value" style={{ color: (posture.shoulder_spread_change || 0) < -0.15 ? 'var(--error)' : 'var(--success)' }}>
                                {posture.shoulder_spread_change.toFixed(4)}
                            </span>
                            <span className="da-detail-note">{(posture.shoulder_spread_change || 0) < -0.15 ? 'Shoulders came together (hunching)' : 'Maintained shoulder width'}</span>
                        </div>
                    )}
                    {posture.shoulder_stability != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Stability</span>
                            <span className="da-detail-value" style={{ color: scoreColor((posture.shoulder_stability || 0) * 100) }}>
                                {((posture.shoulder_stability || 0) * 100).toFixed(0)}%
                            </span>
                            <span className="da-detail-note">How steady your shoulders stayed</span>
                        </div>
                    )}
                    {/* Face-position fallback fields */}
                    {posture.face_y_drift != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Face Y Drift</span>
                            <span className="da-detail-value" style={{ color: (posture.face_y_drift || 0) > 0.05 ? 'var(--error)' : 'var(--success)' }}>
                                {posture.face_y_drift.toFixed(4)}
                            </span>
                            <span className="da-detail-note">{(posture.face_y_drift || 0) > 0.05 ? 'Face dropped — slouching' : 'Stable head position'}</span>
                        </div>
                    )}
                    {posture.face_stability != null && (
                        <div className="da-detail-item">
                            <span className="da-detail-label">Face Stability</span>
                            <span className="da-detail-value" style={{ color: scoreColor((posture.face_stability || 0) * 100) }}>
                                {((posture.face_stability || 0) * 100).toFixed(0)}%
                            </span>
                        </div>
                    )}
                </div>
                {posture.method && (
                    <div className="da-method-note">Analysis method: {posture.method === 'mediapipe_pose' ? '🦴 MediaPipe Pose (shoulder-based)' : '👤 Face-position fallback'}</div>
                )}
            </div>

            {/* Posture Frame Gallery */}
            {postureFrames.length > 0 && (
                <div className="da-subsection">
                    <div className="da-subsection-title">
                        Frame-by-Frame Posture
                        <span className="da-count-badge" style={{ background: 'rgba(129,140,248,0.15)', color: 'var(--accent-primary)' }}>
                            {postureFrames.length} frames
                        </span>
                    </div>
                    <div className="da-frame-gallery">
                        {postureFrames.map((pf, i) => (
                            <div
                                key={i}
                                className={`da-frame-card ${pf.posture_zone || 'aligned'}`}
                                onClick={() => setExpandedFrame(pf)}
                            >
                                <img
                                    src={`data:image/jpeg;base64,${pf.base64_image}`}
                                    alt={`Posture at ${fmtTime(pf.timestamp)}`}
                                    className="da-frame-img"
                                />
                                <div className="da-frame-overlay">
                                    <span className="da-frame-time">{fmtTime(pf.timestamp)}</span>
                                    <span className={`da-frame-badge ${pf.posture_zone || 'aligned'}`}>
                                        {pf.posture_zone === 'below' ? '↓ Below' : pf.posture_zone === 'above' ? '↑ Above' : '✓ Aligned'}
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                    <div className="da-method-note">Click any frame to expand • Lines show detected shoulder position</div>
                </div>
            )}

            {/* Expanded Frame Modal */}
            {expandedFrame && (
                <div className="da-frame-modal" onClick={() => setExpandedFrame(null)}>
                    <div className="da-frame-modal-content" onClick={e => e.stopPropagation()}>
                        <img
                            src={`data:image/jpeg;base64,${expandedFrame.base64_image}`}
                            alt={`Posture at ${fmtTime(expandedFrame.timestamp)}`}
                            className="da-frame-modal-img"
                        />
                        <div className="da-frame-modal-info">
                            <span className="da-frame-time">{fmtTime(expandedFrame.timestamp)}</span>
                            <span className={`da-frame-badge ${expandedFrame.posture_zone || 'aligned'}`}>
                                {expandedFrame.posture_zone === 'below' ? '↓ Below — Low Confidence' : expandedFrame.posture_zone === 'above' ? '↑ Above — Too High' : '✓ Aligned — Confident'}
                            </span>
                            {expandedFrame.shoulder_slope > 0 && (
                                <span className="da-frame-slope">Slope: {expandedFrame.shoulder_slope.toFixed(4)}</span>
                            )}
                        </div>
                        <button className="da-frame-close" onClick={() => setExpandedFrame(null)}>✕</button>
                    </div>
                </div>
            )}

            {/* Eye Contact */}
            <div className="da-subsection">
                <div className="da-subsection-title">
                    Eye Contact & Gaze
                    <span className="da-count-badge" style={{ background: (eyeContact.looking_at_camera_pct || 0) >= 60 ? 'rgba(52,211,153,0.15)' : 'rgba(248,113,113,0.15)', color: (eyeContact.looking_at_camera_pct || 0) >= 60 ? 'var(--success)' : 'var(--error)' }}>
                        {(eyeContact.looking_at_camera_pct || 0).toFixed(0)}% at camera
                    </span>
                </div>

                <MetricBar label="Eye Contact Score" value={eyeContact.eye_contact_score || 0} />

                <div className="da-stats-row">
                    <StatPill icon="👁️" label="Looking at camera" value={`${(eyeContact.looking_at_camera_pct || 0).toFixed(1)}%`} color={(eyeContact.looking_at_camera_pct || 0) >= 60 ? 'var(--success)' : 'var(--warning)'} />
                    <StatPill icon="😴" label="Drowsy frames" value={eyeContact.possible_drowsy_frames || 0} color={(eyeContact.possible_drowsy_frames || 0) > 3 ? 'var(--error)' : 'var(--success)'} />
                    <StatPill icon="👀" label="Avg EAR" value={(eyeContact.avg_ear || 0).toFixed(3)} />
                    <StatPill icon="🔢" label="Frames analyzed" value={eyeContact.total_frames_analyzed || 0} />
                </div>

                {(eyeContact.looking_at_camera_pct || 0) < 50 && (
                    <div className="da-inline-tip">💡 You looked away from the camera more than half the time. Try focusing on the webcam lens while speaking.</div>
                )}
            </div>

            {/* Emotions */}
            <div className="da-subsection">
                <div className="da-subsection-title">Emotion Analysis</div>
                <div className="da-stats-row">
                    <StatPill icon="😊" label="Dominant emotion" value={emotions.dominant_emotion || '—'} color="var(--accent-primary)" />
                    <StatPill icon="🎯" label="Frames analyzed" value={emotions.total_analyzed || 0} />
                </div>
                {emotionEntries.length > 0 && (
                    <div className="da-emotion-bars">
                        {emotionEntries.map(([emotion, count]) => (
                            <div key={emotion} className="da-emotion-item">
                                <span className="da-emotion-label">{emotion}</span>
                                <div className="da-bar-track" style={{ flex: 1 }}>
                                    <div className="da-bar-fill" style={{ width: `${totalEmotionFrames > 0 ? (count / totalEmotionFrames) * 100 : 0}%`, background: emotion === 'happy' ? 'var(--success)' : emotion === 'neutral' ? 'var(--info)' : emotion === 'sad' || emotion === 'fear' ? 'var(--warning)' : emotion === 'angry' || emotion === 'disgust' ? 'var(--error)' : 'var(--accent-secondary)' }} />
                                </div>
                                <span className="da-emotion-count">{count}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

/* ───────────────────────────────────────────────────
   NLP DEEP ANALYSIS SECTION
   ─────────────────────────────────────────────────── */
function NlpDeepAnalysis({ nlp }) {
    if (!nlp) return null;
    return (
        <div className="da-section">
            <div className="da-section-title">
                <span className="da-section-icon">🧠</span> Answer Quality Analysis
            </div>
            <div className="da-scores-row">
                <MetricBar label="Relevance" value={nlp.relevance_score || 0} />
                <MetricBar label="Completeness" value={nlp.completeness_score || 0} />
                <MetricBar label="Communication" value={nlp.communication_score || 0} />
                <MetricBar label="Technical" value={nlp.technical_score || 0} />
            </div>
            {(nlp.keywords || []).length > 0 && (
                <div className="da-subsection">
                    <div className="da-subsection-title">Keywords Detected</div>
                    <div className="da-filler-freq">
                        {nlp.keywords.map((kw, i) => (
                            <span key={i} className="da-filler-tag" style={{ borderColor: 'var(--info)' }}>
                                <span className="da-filler-word">{kw}</span>
                            </span>
                        ))}
                    </div>
                </div>
            )}
            <div className="da-stats-row">
                {nlp.strengths && <StatPill icon="✅" label="Strength" value={nlp.strengths} color="var(--success)" />}
                {nlp.improvement && <StatPill icon="📈" label="To improve" value={nlp.improvement} color="var(--warning)" />}
            </div>
            <div className="da-method-note">Analysis: {nlp.analysis_method === 'groq_llm' ? '🤖 Groq LLM' : '📏 Rule-based'}</div>
        </div>
    );
}


/* ═══════════════════════════════════════════════════
   MAIN REPORT PAGE
   ═══════════════════════════════════════════════════ */
export default function ReportPage() {
    const { sessionId } = useParams();
    const navigate = useNavigate();
    const [report, setReport] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [expandedQ, setExpandedQ] = useState(null);
    const [isDSA, setIsDSA] = useState(false);

    useEffect(() => {
        const load = async () => {
            try {
                // Try regular report first
                const res = await getReport(sessionId);
                const data = res.data;
                // Check if this is a DSA session
                if (data?.session?.interview_type === 'dsa') {
                    // Load DSA-specific report
                    const dsaRes = await getDSAReport(sessionId);
                    setReport(dsaRes.data);
                    setIsDSA(true);
                } else {
                    setReport(data);
                    if (data?.responses?.length > 0) {
                        setExpandedQ(data.responses[0].id);
                    }
                }
            } catch (err) {
                // Maybe it's a DSA session without a FeedbackReport
                try {
                    const dsaRes = await getDSAReport(sessionId);
                    setReport(dsaRes.data);
                    setIsDSA(true);
                } catch {
                    setError('Failed to load report');
                }
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [sessionId]);

    if (loading) {
        return (
            <div className="loading-page">
                <div className="spinner" />
                <p>Loading your report...</p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="page">
                <div className="alert alert-error">{error}</div>
                <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>
                    Back to Dashboard
                </button>
            </div>
        );
    }

    /* ─── DSA Report Renderer ─── */
    if (isDSA && report) {
        const avgScore = report.average_score || 0;
        const sc2 = scoreClass(avgScore);
        return (
            <div className="page">
                <div className="page-header">
                    <h1 className="page-title">DSA Challenge Report</h1>
                    <p className="page-subtitle">
                        {report.questions_answered} of {report.total_questions} questions answered
                    </p>
                </div>

                {/* Overall Score */}
                <div className="card" style={{ textAlign: 'center', marginBottom: '2rem' }}>
                    <div className="card-header"><div className="card-title">Average Score</div></div>
                    <div className={`score-circle ${sc2}`}>{Math.round(avgScore)}</div>
                    <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem', fontSize: '0.9rem' }}>
                        {avgScore >= 75 ? 'Excellent problem-solving!' : avgScore >= 55 ? 'Good approach!' : avgScore >= 35 ? 'Room for improvement' : 'Keep practicing!'}
                    </p>
                </div>

                {/* Per-question results */}
                {(report.questions || []).map((q, i) => {
                    const ev = q.evaluation;
                    const isExpanded2 = expandedQ === q.question_id;
                    return (
                        <div key={q.question_id} className="card da-question-card" style={{ marginBottom: '1rem' }}>
                            <div className="da-question-header" onClick={() => setExpandedQ(isExpanded2 ? null : q.question_id)}>
                                <div className="da-question-left">
                                    <span className="da-question-num">Q{i + 1}</span>
                                    <span className="da-question-text">{q.title}</span>
                                    <span className={`difficulty-badge badge-${q.difficulty}`}>{q.difficulty}</span>
                                    <span className="topic-tag">{q.topic}</span>
                                </div>
                                <div className="da-question-right">
                                    <span className="da-question-score" style={{ color: scoreColor(ev?.overall_score || 0) }}>
                                        {Math.round(ev?.overall_score || 0)}
                                    </span>
                                    <span className={`da-chevron ${isExpanded2 ? 'open' : ''}`}>▾</span>
                                </div>
                            </div>

                            {isExpanded2 && (
                                <div className="da-question-body">
                                    {q.approach_text && (
                                        <div className="da-transcript">
                                            <div className="da-subsection-title">Your Approach</div>
                                            <pre className="dsa-problem-description" style={{ maxHeight: '200px' }}>{q.approach_text}</pre>
                                        </div>
                                    )}
                                    {ev && (
                                        <>
                                            <div className="da-scores-row" style={{ marginTop: '1rem' }}>
                                                <MetricBar label="Correctness" value={ev.score_correctness} max={100} />
                                                <MetricBar label="Time Complexity" value={ev.score_time_complexity} max={100} />
                                                <MetricBar label="Space Complexity" value={ev.score_space_complexity} max={100} />
                                                <MetricBar label="Edge Cases" value={ev.score_edge_cases} max={100} />
                                                <MetricBar label="Clarity" value={ev.score_clarity} max={100} />
                                            </div>
                                            {ev.time_complexity_analysis && (
                                                <div className="dsa-complexity-analysis" style={{ marginTop: '1rem' }}>
                                                    <span className="dsa-complexity-label">Complexity:</span>
                                                    <span className="dsa-complexity-value">{ev.time_complexity_analysis}</span>
                                                </div>
                                            )}
                                            {ev.feedback && (
                                                <div className="dsa-feedback-panel" style={{ marginTop: '1rem' }}>
                                                    <h4>📝 Feedback</h4>
                                                    <p>{ev.feedback}</p>
                                                </div>
                                            )}
                                            {ev.optimal_approach && (
                                                <div className="dsa-optimal-panel">
                                                    <h4>✨ Optimal Approach</h4>
                                                    <p>{ev.optimal_approach}</p>
                                                </div>
                                            )}
                                        </>
                                    )}
                                    {!ev && <p style={{ color: 'var(--text-muted)' }}>Not answered</p>}
                                </div>
                            )}
                        </div>
                    );
                })}

                <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '2rem' }}>
                    <Link to="/select" className="btn btn-primary">Practice Again</Link>
                    <Link to="/dashboard" className="btn btn-secondary">Back to Dashboard</Link>
                </div>
            </div>
        );
    }

    const feedback = report?.feedback;
    const score = feedback?.overall_score || 0;
    const sc = scoreClass(score);

    const radarData = [
        { metric: 'Voice', value: feedback?.score_breakdown?.voice || 0 },
        { metric: 'Content', value: feedback?.score_breakdown?.nlp || 0 },
        { metric: 'Presence', value: feedback?.score_breakdown?.facial || 0 },
    ];

    return (
        <div className="page">
            <div className="page-header">
                <h1 className="page-title">Interview Report</h1>
                <p className="page-subtitle">
                    {report?.session?.interview_type?.toUpperCase()} Interview — {report?.responses?.length} questions answered
                </p>
            </div>

            {/* ──── Overview ──── */}
            <div className="grid-2" style={{ marginBottom: '2rem' }}>
                {/* Overall Score */}
                <div className="card" style={{ textAlign: 'center' }}>
                    <div className="card-header">
                        <div className="card-title">Overall Score</div>
                    </div>
                    <div className={`score-circle ${sc}`}>
                        {Math.round(score)}
                    </div>
                    <p style={{ color: 'var(--text-secondary)', marginTop: '0.75rem', fontSize: '0.9rem' }}>
                        {score >= 75 ? 'Excellent performance!' : score >= 55 ? 'Good job, keep improving!' : score >= 35 ? 'Room for improvement' : 'Keep practicing!'}
                    </p>
                </div>

                {/* Radar Chart */}
                <div className="card">
                    <div className="card-header">
                        <div className="card-title">Score Breakdown</div>
                    </div>
                    <ResponsiveContainer width="100%" height={250}>
                        <RadarChart data={radarData}>
                            <PolarGrid stroke="rgba(255,255,255,0.1)" />
                            <PolarAngleAxis dataKey="metric" tick={{ fill: '#94a3b8', fontSize: 13 }} />
                            <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                            <Radar
                                dataKey="value"
                                stroke="#818cf8"
                                fill="#818cf8"
                                fillOpacity={0.25}
                                strokeWidth={2}
                            />
                        </RadarChart>
                    </ResponsiveContainer>

                    <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 0 }}>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--info)' }}>
                                {Math.round(feedback?.score_breakdown?.voice || 0)}%
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Voice</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--success)' }}>
                                {Math.round(feedback?.score_breakdown?.nlp || 0)}%
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Content</div>
                        </div>
                        <div style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: '1.2rem', fontWeight: 700, color: 'var(--accent-tertiary)' }}>
                                {Math.round(feedback?.score_breakdown?.facial || 0)}%
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Presence</div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ──── Feedback ──── */}
            <div className="grid-3" style={{ marginBottom: '2rem' }}>
                <div className="card">
                    <div className="card-header">
                        <div className="card-title" style={{ color: 'var(--success)' }}>✦ Strengths</div>
                    </div>
                    <ul className="feedback-list">
                        {(feedback?.strengths || []).map((s, i) => (
                            <li key={i}><span className="feedback-icon">✓</span> {s}</li>
                        ))}
                        {(!feedback?.strengths?.length) && <li style={{ color: 'var(--text-muted)' }}>No strengths identified yet</li>}
                    </ul>
                </div>
                <div className="card">
                    <div className="card-header">
                        <div className="card-title" style={{ color: 'var(--warning)' }}>⚡ Areas to Improve</div>
                    </div>
                    <ul className="feedback-list">
                        {(feedback?.weaknesses || []).map((w, i) => (
                            <li key={i}><span className="feedback-icon">!</span> {w}</li>
                        ))}
                        {(!feedback?.weaknesses?.length) && <li style={{ color: 'var(--text-muted)' }}>No weaknesses found</li>}
                    </ul>
                </div>
                <div className="card">
                    <div className="card-header">
                        <div className="card-title" style={{ color: 'var(--info)' }}>💡 Suggestions</div>
                    </div>
                    <ul className="feedback-list">
                        {(feedback?.suggestions || []).map((s, i) => (
                            <li key={i}><span className="feedback-icon">→</span> {s}</li>
                        ))}
                    </ul>
                </div>
            </div>

            {/* ──── Per-question Deep Analysis ──── */}
            <div style={{ marginBottom: '2rem' }}>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, marginBottom: '1rem', color: 'var(--text-primary)' }}>
                    Question-by-Question Deep Analysis
                </h2>

                {(report?.responses || []).map((r, i) => {
                    const isExpanded = expandedQ === r.id;
                    const a = r.analysis || {};
                    return (
                        <div key={r.id} className="card da-question-card" style={{ marginBottom: '1rem' }}>
                            {/* Collapsible header */}
                            <div
                                className="da-question-header"
                                onClick={() => setExpandedQ(isExpanded ? null : r.id)}
                            >
                                <div className="da-question-left">
                                    <span className="da-question-num">Q{i + 1}</span>
                                    <span className="da-question-text">{r.question_text}</span>
                                </div>
                                <div className="da-question-right">
                                    <span className="da-question-score" style={{ color: scoreColor((a.overall_score || 0) * 100) }}>
                                        {Math.round((a.overall_score || 0) * 100)}%
                                    </span>
                                    <span className={`da-chevron ${isExpanded ? 'open' : ''}`}>▾</span>
                                </div>
                            </div>

                            {isExpanded && (
                                <div className="da-question-body">
                                    {/* Transcript */}
                                    {r.transcript && (
                                        <div className="da-transcript">
                                            <div className="da-subsection-title">Your Answer (Transcript)</div>
                                            <p className="da-transcript-text">{r.transcript}</p>
                                        </div>
                                    )}

                                    {/* Score pills */}
                                    <div className="da-mini-scores">
                                        <span className="da-mini-pill" style={{ borderColor: scoreColor((a.voice_overall || 0) * 100) }}>
                                            🎙️ Voice {Math.round((a.voice_overall || 0) * 100)}%
                                        </span>
                                        <span className="da-mini-pill" style={{ borderColor: scoreColor((a.nlp_overall || 0) * 100) }}>
                                            🧠 Content {Math.round((a.nlp_overall || 0) * 100)}%
                                        </span>
                                        <span className="da-mini-pill" style={{ borderColor: scoreColor((a.facial_overall || 0) * 100) }}>
                                            📹 Presence {Math.round((a.facial_overall || 0) * 100)}%
                                        </span>
                                    </div>

                                    {/* Deep Analysis Sections */}
                                    <VoiceDeepAnalysis voice={a.voice_raw} />
                                    <NlpDeepAnalysis nlp={a.nlp_raw} />
                                    <VideoDeepAnalysis facial={a.facial_raw} />
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                <Link to="/select" className="btn btn-primary">Practice Again</Link>
                <Link to="/dashboard" className="btn btn-secondary">Back to Dashboard</Link>
            </div>
        </div>
    );
}
