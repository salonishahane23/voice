import streamlit as st
import numpy as np
import whisper
import librosa
from sklearn.ensemble import RandomForestClassifier
import sounddevice as sd
import soundfile as sf
import tempfile
import os
from datetime import datetime
import json

FILLER_WORDS = [
    "uh", "um", "erm", "like", "you know", "actually",
    "basically", "so", "well", "hmm"
]


# Page configuration
st.set_page_config(
    page_title="Voice Confidence Analyzer",
    page_icon="🎙️",
    layout="wide"
)

# Initialize session state
if 'recording' not in st.session_state:
    st.session_state.recording = False
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = None
if 'sample_rate' not in st.session_state:
    st.session_state.sample_rate = 16000

# Load Whisper model (cached)
@st.cache_resource
def load_whisper_model():
    return whisper.load_model('base')

# Train demo confidence model (cached)
@st.cache_resource
def train_demo_model():
    np.random.seed(42)
    X_demo = np.random.rand(40, 4) * 0.5 + np.random.choice([0, 1], (40, 4))
    y_demo = np.array([1]*20 + [0]*20)
    
    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X_demo, y_demo)
    return clf

def extract_features_whisper(result):
    """Extract 4 key features from Whisper result for confidence prediction"""
    segs = result['segments']
    if not segs:
        return np.zeros(4)

    avg_logprobs = [s['avg_logprob'] for s in segs]
    
    total_dur = segs[-1]['end'] - segs[0]['start']
    total_words = sum(len(s['text'].split()) for s in segs)
    wps = total_words / total_dur if total_dur > 0 else 0.0
    
    pauses = [
        max(0.0, cur['start'] - prev['end'])
        for prev, cur in zip(segs, segs[1:])
    ]
    avg_pause = np.mean(pauses) if pauses else 0.0
    
    return np.array([
        np.mean(avg_logprobs),
        np.std(avg_logprobs),
        wps,
        avg_pause
    ])

def heuristic_confidence(result):
    """Rule-based confidence score"""
    segs = result['segments']
    if not segs:
        return 0.5
    
    avg_logprob = np.mean([s['avg_logprob'] for s in segs])
    total_dur = segs[-1]['end'] - segs[0]['start']
    total_words = sum(len(s['text'].split()) for s in segs)
    wps = total_words / total_dur if total_dur > 0 else 0
    
    score = (np.exp(avg_logprob) + min(wps / 5.0, 1.0)) / 2
    return np.clip(score, 0.0, 1.0)

def record_audio(duration, sample_rate=16000, device=None):
    """Record audio from microphone"""
    st.info(f"🎙️ Recording for {duration} seconds... Speak now!")
    
    # Use specified device or default
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype='float32',
        device=device
    )
    
    # Show progress bar
    progress_bar = st.progress(0)
    for i in range(duration):
        import time
        time.sleep(1)
        progress_bar.progress((i + 1) / duration)
    
    sd.wait()
    progress_bar.empty()
    return recording.flatten(), sample_rate

def detect_filler_words(text):
    text_lower = text.lower()
    fillers_found = []

    for filler in FILLER_WORDS:
        if filler in text_lower:
            fillers_found.append(filler)

    return fillers_found

def detect_stuttering(text):
    words = text.lower().split()
    repeated = []

    for i in range(len(words) - 1):
        if words[i] == words[i + 1]:
            repeated.append(words[i])

    return repeated

def analyze_loudness(audio_segment, sr):
    """Analyze loudness of an audio segment"""
    if len(audio_segment) == 0:
        return "unknown", 0.0
    
    # Calculate RMS energy
    rms = np.sqrt(np.mean(audio_segment**2))
    
    # Define thresholds (these can be adjusted based on your needs)
    if rms < 0.01:
        return "quiet", rms
    elif rms > 0.1:
        return "loud", rms
    else:
        return "normal", rms

def get_audio_devices():
    """Get list of available audio input devices"""
    devices = sd.query_devices()
    input_devices = []
    for i, device in enumerate(devices):
        if device['max_input_channels'] > 0:
            input_devices.append({
                'index': i,
                'name': device['name'],
                'channels': device['max_input_channels']
            })
    return input_devices

def analyze_audio(audio_file_path):
    """Complete analysis pipeline"""
    model = load_whisper_model()
    clf = train_demo_model()
    
    # Transcribe
    with st.spinner("🔄 Transcribing audio..."):
        result = model.transcribe(
            audio_file_path,
            word_timestamps=True,
            temperature=0
        )
    
    # Extract features
    features = extract_features_whisper(result)
    
    # Get scores
    heur_score = heuristic_confidence(result)
    model_score = clf.predict_proba(features.reshape(1, -1))[0][1]
    
    # Audio analysis
    y_audio, sr = librosa.load(audio_file_path, sr=None)
    energy = librosa.feature.rms(y=y_audio)[0]
    pitch, _ = librosa.piptrack(y=y_audio, sr=sr)
    pitch_vals = pitch[pitch > 0][:1000]
    
    # Detailed segment analysis
    detailed_segments = []
    
    for seg in result["segments"]:
        start_sample = int(seg["start"] * sr)
        end_sample = int(seg["end"] * sr)
        segment_audio = y_audio[start_sample:end_sample]

        # Text analysis
        fillers = detect_filler_words(seg["text"])
        stutters = detect_stuttering(seg["text"])

        # Audio analysis
        loudness_label, loudness_value = analyze_loudness(segment_audio, sr)

        # Confidence heuristic per segment
        confidence_penalty = 0
        confidence_penalty += len(fillers) * 0.1
        confidence_penalty += len(stutters) * 0.15
        if loudness_label != "normal":
            confidence_penalty += 0.1

        confidence_score = max(0.0, 1.0 - confidence_penalty)

        detailed_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip(),
            "fillers": fillers,
            "stutters": stutters,
            "loudness": loudness_label,
            "confidence": confidence_score
        })
    
    return {
        'result': result,
        'heur_score': heur_score,
        'model_score': model_score,
        'energy_mean': energy.mean(),
        'energy_std': energy.std(),
        'pitch_min': pitch_vals.min() if len(pitch_vals) > 0 else 0,
        'pitch_max': pitch_vals.max() if len(pitch_vals) > 0 else 0,
        'detailed_segments': detailed_segments
    }


# Main UI
st.title("🎙️ Voice Confidence Analyzer")
st.markdown("### Record your voice and get instant confidence analysis")

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Recording Settings")
    
    # Get available microphones
    audio_devices = get_audio_devices()
    
    if audio_devices:
        device_names = [f"{d['name']} (ID: {d['index']})" for d in audio_devices]
        selected_device_name = st.selectbox(
            "🎤 Select Microphone",
            options=device_names,
            help="Choose your microphone device"
        )
        selected_device = audio_devices[device_names.index(selected_device_name)]['index']
    else:
        st.error("❌ No microphone devices found!")
        selected_device = None
    
    # Test microphone button
    if st.button("🔊 Test Microphone"):
        if selected_device is not None:
            st.info("Testing microphone... Speak now!")
            test_audio = sd.rec(
                int(2 * 16000),
                samplerate=16000,
                channels=1,
                dtype='float32',
                device=selected_device
            )
            sd.wait()
            
            # Check if audio was captured
            max_amplitude = np.max(np.abs(test_audio))
            if max_amplitude > 0.01:
                st.success(f"✅ Microphone working! Level: {max_amplitude:.3f}")
                st.audio(test_audio.flatten(), sample_rate=16000)
            else:
                st.warning("⚠️ Very low audio detected. Check microphone permissions and volume.")
    
    st.markdown("---")
    
    duration = st.slider("Recording Duration (seconds)", 5, 60, 15)
    sample_rate = st.selectbox("Sample Rate", [16000, 22050, 44100], index=0)
    st.session_state.sample_rate = sample_rate
    
    st.markdown("---")
    st.markdown("### 📊 About")
    st.info("""
    This app analyzes your speech for:
    - **Fluency**: Speech smoothness
    - **Confidence**: Based on ML model
    - **Speaking Rate**: Words per second
    - **Voice Energy**: Volume consistency
    """)
    
    st.markdown("---")
    st.markdown("### 🔧 Troubleshooting")
    with st.expander("Common Issues"):
        st.markdown("""
        - Check microphone permissions
        - Ensure correct device is selected
        - Test microphone before recording
        - Check volume levels
        """)
    
    # Show default device info
    st.markdown("---")
    st.caption(f"**Default device:** {sd.query_devices(kind='input')['name']}")

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("🎤 Recording Control")
    
    if st.button("🔴 Start Recording", type="primary", use_container_width=True):
        try:
            audio_data, sr = record_audio(duration, sample_rate, device=selected_device)
            
            # Check if audio was actually recorded
            max_amplitude = np.max(np.abs(audio_data))
            
            if max_amplitude < 0.001:
                st.error("❌ No audio detected! Please check:")
                st.markdown("""
                - Microphone permissions in Windows Settings
                - Microphone is not muted
                - Correct microphone is selected
                - Volume levels are adequate
                """)
            else:
                st.session_state.audio_data = audio_data
                st.session_state.sample_rate = sr
                st.success(f"✅ Recording complete! Max level: {max_amplitude:.3f}")
                
        except Exception as e:
            st.error(f"❌ Recording error: {str(e)}")
            st.info("💡 Try selecting a different microphone from the sidebar")
    
    if st.session_state.audio_data is not None:
        st.markdown("#### 🎧 Playback")
        st.audio(st.session_state.audio_data, sample_rate=st.session_state.sample_rate)
        
        # Show audio stats
        max_amp = np.max(np.abs(st.session_state.audio_data))
        st.caption(f"Audio level: {max_amp:.4f} | Duration: {len(st.session_state.audio_data)/st.session_state.sample_rate:.1f}s")

with col2:
    st.subheader("🔍 Analysis")
    
    if st.session_state.audio_data is not None:
        if st.button("📊 Analyze Recording", type="secondary", use_container_width=True):
            # Save audio to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                sf.write(tmp_file.name, st.session_state.audio_data, st.session_state.sample_rate)
                temp_path = tmp_file.name
            
            try:
                # Analyze
                analysis = analyze_audio(temp_path)
                
                # Display results
                st.markdown("---")
                st.markdown("### 📝 Transcript")
                st.markdown(f"**Full Text:**")
                st.write(analysis['result']['text'])
                
                st.markdown("---")
                st.markdown("### 📈 Confidence Scores")
                
                score_col1, score_col2 = st.columns(2)
                with score_col1:
                    st.metric("Heuristic Confidence", f"{analysis['heur_score']:.1%}")
                with score_col2:
                    st.metric("ML Model Confidence", f"{analysis['model_score']:.1%}")
                
                st.markdown("---")
                st.markdown("### 🎵 Voice Characteristics")
                
                char_col1, char_col2 = st.columns(2)
                with char_col1:
                    st.metric("Energy Mean", f"{analysis['energy_mean']:.3f}")
                    st.metric("Energy Std Dev", f"{analysis['energy_std']:.3f}")
                with char_col2:
                    if analysis['pitch_min'] > 0:
                        st.metric("Pitch Range", f"{analysis['pitch_min']:.0f} - {analysis['pitch_max']:.0f} Hz")
                    else:
                        st.info("Pitch data unavailable")
                
                st.markdown("---")
                st.markdown("### 🔍 Sentence-wise Voice Feedback")
                with st.expander("View detailed analysis per segment"):
                    for seg in analysis["detailed_segments"]:
                        st.markdown(
                            f"""
                            **[{seg['start']:.2f}s – {seg['end']:.2f}s]**  
                            _"{seg['text']}"_

                            • 🎯 Confidence: **{seg['confidence']*100:.0f}%**  
                            • 🔊 Loudness: **{seg['loudness']}**  
                            • 🧠 Filler words: **{', '.join(seg['fillers']) if seg['fillers'] else 'None'}**  
                            • 🪜 Stuttering: **{', '.join(seg['stutters']) if seg['stutters'] else 'None'}**
                            ---
                            """
                        )
                
                st.markdown("---")
                st.markdown("### ⏱️ Timestamped Transcript")
                
                with st.expander("View detailed timestamps"):
                    for seg in analysis['result']['segments']:
                        st.markdown(
                            f"**[{seg['start']:.2f}s - {seg['end']:.2f}s]** {seg['text'].strip()}"
                        )
                
                # Download options
                st.markdown("---")
                st.markdown("### 💾 Download Results")
                
                download_col1, download_col2, download_col3 = st.columns(3)
                
                with download_col1:
                    transcript_text = analysis['result']['text']
                    st.download_button(
                        "📄 Plain Transcript",
                        transcript_text,
                        file_name=f"transcript_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                
                with download_col2:
                    timestamped = "\n".join([
                        f"[{seg['start']:.2f}s - {seg['end']:.2f}s] {seg['text'].strip()}"
                        for seg in analysis['result']['segments']
                    ])
                    st.download_button(
                        "⏱️ Timestamped",
                        timestamped,
                        file_name=f"timestamped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                
                with download_col3:
                    json_data = json.dumps(analysis['result'], indent=2)
                    st.download_button(
                        "📦 Full JSON",
                        json_data,
                        file_name=f"full_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )
                
            finally:
                # Cleanup
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray;'>"
    "💡 Higher confidence scores indicate more fluent and assured speech"
    "</div>",
    unsafe_allow_html=True
)