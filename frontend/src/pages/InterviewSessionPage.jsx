import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { startInterview, submitResponse, getNextQuestion, endInterview } from '../services/api';
import { PoseLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

export default function InterviewSessionPage() {
    const { type } = useParams();
    const navigate = useNavigate();

    const [session, setSession] = useState(null);
    const [question, setQuestion] = useState(null);
    const [loading, setLoading] = useState(true);
    const [recording, setRecording] = useState(false);
    const [timer, setTimer] = useState(0);
    const [submitting, setSubmitting] = useState(false);
    const [finished, setFinished] = useState(false);
    const [error, setError] = useState('');
    const [postureZone, setPostureZone] = useState('waiting'); // waiting|aligned|below|above

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const streamRef = useRef(null);
    const chunksRef = useRef([]);
    const timerRef = useRef(null);

    // Posture detection refs
    const poseLandmarkerRef = useRef(null);
    const rafRef = useRef(null);
    const thresholdYRef = useRef(null);
    const calibrationFrames = useRef([]);
    const isDetectingRef = useRef(false);

    // Start interview session
    useEffect(() => {
        const init = async () => {
            try {
                const res = await startInterview(type, 5);
                setSession(res.data.session);
                setQuestion(res.data.question);
            } catch (err) {
                setError('Failed to start interview');
            } finally {
                setLoading(false);
            }
        };
        init();

        return () => {
            if (streamRef.current) {
                streamRef.current.getTracks().forEach(t => t.stop());
            }
            if (timerRef.current) clearInterval(timerRef.current);
            if (rafRef.current) cancelAnimationFrame(rafRef.current);
            isDetectingRef.current = false;
        };
    }, [type]);

    // Initialize MediaPipe PoseLandmarker
    useEffect(() => {
        const initPose = async () => {
            try {
                const vision = await FilesetResolver.forVisionTasks(
                    'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
                );
                const landmarker = await PoseLandmarker.createFromOptions(vision, {
                    baseOptions: {
                        modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task',
                        delegate: 'GPU',
                    },
                    runningMode: 'VIDEO',
                    numPoses: 1,
                });
                poseLandmarkerRef.current = landmarker;
                console.log('[POSTURE] PoseLandmarker initialized');
            } catch (err) {
                console.warn('[POSTURE] Failed to init PoseLandmarker:', err);
            }
        };
        initPose();
    }, []);

    // Request camera+mic
    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true,
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch {
            setError('Camera/Microphone permission denied');
        }
    };

    useEffect(() => {
        if (!loading && session) startCamera();
    }, [loading, session]);

    // --- Posture detection loop ---
    const detectPosture = useCallback(() => {
        if (!isDetectingRef.current) return;
        const video = videoRef.current;
        const canvas = canvasRef.current;
        const landmarker = poseLandmarkerRef.current;

        if (!video || !canvas || !landmarker || video.readyState < 2) {
            rafRef.current = requestAnimationFrame(detectPosture);
            return;
        }

        const ctx = canvas.getContext('2d');
        const vw = video.videoWidth || video.clientWidth;
        const vh = video.videoHeight || video.clientHeight;
        canvas.width = vw;
        canvas.height = vh;

        // Run pose detection
        let results;
        try {
            results = landmarker.detectForVideo(video, performance.now());
        } catch {
            rafRef.current = requestAnimationFrame(detectPosture);
            return;
        }

        ctx.clearRect(0, 0, vw, vh);

        if (results.landmarks && results.landmarks.length > 0) {
            const landmarks = results.landmarks[0];
            // Landmarks 11 = left shoulder, 12 = right shoulder (normalized 0-1)
            const leftShoulder = landmarks[11];
            const rightShoulder = landmarks[12];

            if (leftShoulder && rightShoulder) {
                const lx = leftShoulder.x * vw;
                const ly = leftShoulder.y * vh;
                const rx = rightShoulder.x * vw;
                const ry = rightShoulder.y * vh;
                const midY = (ly + ry) / 2;

                // Calibration: collect first ~30 frames to establish threshold
                const tolerance = vh * 0.03; // 3% of frame height

                if (calibrationFrames.current.length < 30) {
                    calibrationFrames.current.push(midY);
                    setPostureZone('waiting');

                    // During calibration: draw shoulders in blue
                    ctx.strokeStyle = '#60a5fa';
                    ctx.lineWidth = 3;
                    ctx.beginPath();
                    ctx.moveTo(lx, ly);
                    ctx.lineTo(rx, ry);
                    ctx.stroke();

                    // Shoulder dots
                    [{ x: lx, y: ly }, { x: rx, y: ry }].forEach(({ x, y }) => {
                        ctx.beginPath();
                        ctx.arc(x, y, 6, 0, 2 * Math.PI);
                        ctx.fillStyle = '#60a5fa';
                        ctx.fill();
                    });

                    // Calibration label
                    ctx.fillStyle = 'rgba(0,0,0,0.6)';
                    ctx.fillRect(vw / 2 - 80, 10, 160, 28);
                    ctx.fillStyle = '#60a5fa';
                    ctx.font = 'bold 13px Inter, sans-serif';
                    ctx.textAlign = 'center';
                    ctx.fillText(`Calibrating... ${calibrationFrames.current.length}/30`, vw / 2, 30);
                    ctx.textAlign = 'start';

                    // Set threshold once calibration done
                    if (calibrationFrames.current.length === 30) {
                        const avgY = calibrationFrames.current.reduce((a, b) => a + b, 0) / 30;
                        thresholdYRef.current = avgY;
                        console.log('[POSTURE] Threshold set at Y =', avgY.toFixed(1));
                    }
                } else {
                    // --- Active detection phase ---
                    const thresholdY = thresholdYRef.current;

                    // Classify zone
                    let zone = 'aligned';
                    if (midY > thresholdY + tolerance) zone = 'below';
                    else if (midY < thresholdY - tolerance) zone = 'above';
                    setPostureZone(zone);

                    const zoneColors = {
                        below: '#f87171',
                        aligned: '#34d399',
                        above: '#fbbf24',
                    };
                    const color = zoneColors[zone];

                    // --- Draw green dotted threshold line ---
                    ctx.setLineDash([10, 8]);
                    ctx.strokeStyle = '#34d399';
                    ctx.lineWidth = 2;
                    ctx.beginPath();
                    ctx.moveTo(0, thresholdY);
                    ctx.lineTo(vw, thresholdY);
                    ctx.stroke();
                    ctx.setLineDash([]);

                    // "THRESHOLD" label
                    ctx.fillStyle = '#34d399';
                    ctx.font = 'bold 11px Inter, sans-serif';
                    ctx.fillText('THRESHOLD', vw - 90, thresholdY - 5);

                    // --- Shoulder line ---
                    ctx.strokeStyle = color;
                    ctx.lineWidth = 3;
                    ctx.beginPath();
                    ctx.moveTo(lx, ly);
                    ctx.lineTo(rx, ry);
                    ctx.stroke();

                    // Shoulder dots
                    [{ x: lx, y: ly }, { x: rx, y: ry }].forEach(({ x, y }) => {
                        ctx.beginPath();
                        ctx.arc(x, y, 8, 0, 2 * Math.PI);
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 2;
                        ctx.stroke();
                        ctx.beginPath();
                        ctx.arc(x, y, 4, 0, 2 * Math.PI);
                        ctx.fillStyle = color;
                        ctx.fill();
                    });

                    // Vertical arrow from shoulder midpoint to threshold
                    const midX = (lx + rx) / 2;
                    if (Math.abs(midY - thresholdY) > 5) {
                        ctx.strokeStyle = color;
                        ctx.lineWidth = 2;
                        ctx.beginPath();
                        ctx.moveTo(midX, midY);
                        ctx.lineTo(midX, thresholdY);
                        ctx.stroke();

                        // Arrowhead
                        const dir = thresholdY > midY ? 1 : -1;
                        ctx.beginPath();
                        ctx.moveTo(midX, thresholdY);
                        ctx.lineTo(midX - 5, thresholdY - dir * 8);
                        ctx.lineTo(midX + 5, thresholdY - dir * 8);
                        ctx.closePath();
                        ctx.fillStyle = color;
                        ctx.fill();

                        // Distance text
                        const dist = Math.abs(Math.round(midY - thresholdY));
                        ctx.fillStyle = color;
                        ctx.font = 'bold 11px Inter, sans-serif';
                        ctx.fillText(`${dist}px ${midY > thresholdY ? 'below' : 'above'}`,
                            midX + 10, (midY + thresholdY) / 2);
                    }

                    // Vertical refs from shoulders
                    ctx.strokeStyle = 'rgba(180,180,180,0.5)';
                    ctx.lineWidth = 1;
                    const vLen = vh * 0.1;
                    ctx.beginPath(); ctx.moveTo(lx, ly); ctx.lineTo(lx, ly + vLen); ctx.stroke();
                    ctx.beginPath(); ctx.moveTo(rx, ry); ctx.lineTo(rx, ry + vLen); ctx.stroke();
                }
            }
        }

        rafRef.current = requestAnimationFrame(detectPosture);
    }, []);

    // Start/stop posture detection with recording
    useEffect(() => {
        if (recording && poseLandmarkerRef.current) {
            isDetectingRef.current = true;
            calibrationFrames.current = [];
            thresholdYRef.current = null;
            setPostureZone('waiting');
            detectPosture();
        } else {
            isDetectingRef.current = false;
            if (rafRef.current) cancelAnimationFrame(rafRef.current);
            // Clear canvas
            const canvas = canvasRef.current;
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            setPostureZone('waiting');
        }
    }, [recording, detectPosture]);

    const startRecording = () => {
        if (!streamRef.current) return;
        chunksRef.current = [];

        const mr = new MediaRecorder(streamRef.current, { mimeType: 'video/webm' });
        mr.ondataavailable = (e) => {
            if (e.data.size > 0) chunksRef.current.push(e.data);
        };
        mr.start();
        mediaRecorderRef.current = mr;
        setRecording(true);
        setTimer(0);

        timerRef.current = setInterval(() => {
            setTimer((t) => t + 1);
        }, 1000);
    };

    const stopRecording = () => {
        return new Promise((resolve) => {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
                mediaRecorderRef.current.onstop = () => {
                    const blob = new Blob(chunksRef.current, { type: 'video/webm' });
                    resolve(blob);
                };
                mediaRecorderRef.current.stop();
            } else {
                resolve(null);
            }
            setRecording(false);
            if (timerRef.current) clearInterval(timerRef.current);
        });
    };

    const handleSubmitAnswer = async () => {
        setSubmitting(true);
        try {
            const blob = await stopRecording();

            const formData = new FormData();
            formData.append('question_id', question.id);
            formData.append('question_text', question.text);
            formData.append('transcript', '');
            formData.append('duration_seconds', timer);

            if (blob) {
                formData.append('audio', blob, 'audio.webm');
                formData.append('video', blob, 'video.webm');
            }

            await submitResponse(session.id, formData);

            // Get next question
            const nextRes = await getNextQuestion(session.id);
            if (nextRes.data.status === 'completed') {
                // End interview
                const endRes = await endInterview(session.id);
                setFinished(true);
                navigate(`/report/${session.id}`);
            } else {
                setQuestion(nextRes.data.question);
                setTimer(0);
            }
        } catch (err) {
            setError('Failed to submit answer');
        } finally {
            setSubmitting(false);
        }
    };

    const formatTime = (s) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
    };

    const zoneLabels = {
        waiting: { text: 'Posture tracking will start when you begin recording', icon: '⏳', cls: 'waiting' },
        aligned: { text: 'Aligned — Confident', icon: '✓', cls: 'aligned' },
        below: { text: 'Below — Low Confidence', icon: '↓', cls: 'below' },
        above: { text: 'Above — Too High', icon: '↑', cls: 'above' },
    };
    const currentZone = zoneLabels[postureZone] || zoneLabels.waiting;

    if (loading) {
        return (
            <div className="loading-page">
                <div className="spinner" />
                <p>Preparing your interview...</p>
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
            <div className="interview-container">
                {/* Progress */}
                {question && (
                    <div className="session-progress">
                        <div className="progress-bar-bg">
                            <div
                                className="progress-bar-fill"
                                style={{ width: `${((question.question_number) / question.total_questions) * 100}%` }}
                            />
                        </div>
                        <span className="progress-text">
                            {question.question_number} / {question.total_questions}
                        </span>
                    </div>
                )}

                {error && <div className="alert alert-error">{error}</div>}

                {/* Question Card */}
                <div className="card" style={{ marginBottom: '1.5rem' }}>
                    <div className="question-display">
                        <div className="question-number">
                            Question {question?.question_number} of {question?.total_questions}
                        </div>
                        <div className="question-text">{question?.text}</div>
                        {question?.tips && (
                            <div className="question-tips">Tip: {question.tips}</div>
                        )}
                    </div>
                </div>

                {/* Video + Posture Canvas + Recording */}
                <div className="card">
                    <div className="posture-video-wrapper">
                        <video ref={videoRef} className="video-preview" autoPlay muted playsInline />
                        <canvas ref={canvasRef} className="posture-canvas-overlay" />
                    </div>

                    {/* Live posture status pill */}
                    {recording && postureZone !== 'waiting' && (
                        <div className={`posture-status-pill ${currentZone.cls}`}>
                            <span className="posture-status-icon">{currentZone.icon}</span>
                            <span>{currentZone.text}</span>
                        </div>
                    )}
                    {recording && postureZone === 'waiting' && (
                        <div className="posture-status-pill waiting">
                            <span className="posture-status-icon">⏳</span>
                            <span>Calibrating posture threshold...</span>
                        </div>
                    )}

                    <div className="recording-controls">
                        <div className="timer">{formatTime(timer)}</div>

                        {!recording ? (
                            <button
                                className="record-btn"
                                onClick={startRecording}
                                disabled={submitting}
                                title="Start Recording"
                            >
                                <div className="record-btn-inner" />
                            </button>
                        ) : (
                            <button
                                className="record-btn recording"
                                onClick={handleSubmitAnswer}
                                disabled={submitting}
                                title="Stop & Submit"
                            >
                                <div className="record-btn-inner" />
                            </button>
                        )}

                        <div className={`recording-status ${recording ? 'active' : ''}`}>
                            {submitting ? 'Submitting...' : recording ? 'Recording — click to stop & submit' : 'Click to start recording your answer'}
                        </div>

                        {!recording && timer === 0 && (
                            <button
                                className="btn btn-secondary btn-sm"
                                onClick={() => {
                                    endInterview(session.id).then(() => navigate(`/report/${session.id}`));
                                }}
                            >
                                Skip & End Interview
                            </button>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
