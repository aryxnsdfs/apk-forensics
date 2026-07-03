import { useState, useRef } from 'react';
import { useSimulation } from '../../hooks/useSimulation';
import { useSimulationState, useSimulationDispatch, getApiBase } from '../../store/simulationStore';

const SAMPLE_APKS = [
  { filename: 'test-sms-stealer.apk', label: 'SMS Stealer', desc: 'Intercepts SMS/OTP messages and exfiltrates them.' },
  { filename: 'test-banking-overlay.apk', label: 'Banking Overlay', desc: 'Draws fake login screens over banking apps.' },
  { filename: 'test-spyware.apk', label: 'Spyware', desc: 'Records audio, tracks GPS, harvests contacts.' },
  { filename: 'test-dropper.apk', label: 'Dropper', desc: 'Downloads and installs a second-stage payload.' },
  { filename: 'test-benign.apk', label: 'Benign Flashlight', desc: 'Clean flashlight app — expected to score low.' },
];

export default function CommandPrompt() {
  const { isRunning, scenarioComplete } = useSimulationState();
  const dispatch = useSimulationDispatch();
  const { stop } = useSimulation();
  const [uploading, setUploading] = useState(false);
  const [analyzingSample, setAnalyzingSample] = useState(null);
  const fileInputRef = useRef(null);

  const handleApkUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    dispatch({ type: 'SET_FILE_SIZE', payload: file.size / (1024 * 1024) });
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      await fetch(`${getApiBase()}/api/analyze`, { method: 'POST', body: form });
      // Results stream in over the existing WebSocket (chat / causal / rca / verdict).
    } catch (err) {
      console.error('[CommandPrompt] APK upload failed', err);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleSampleClick = async (sample) => {
    if (analyzingSample) return;
    setAnalyzingSample(sample.filename);
    try {
      await fetch(`${getApiBase()}/api/analyze-sample`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename: sample.filename }),
      });
    } catch (err) {
      console.error('[CommandPrompt] Sample analysis failed', err);
    } finally {
      setAnalyzingSample(null);
    }
  };

  const busy = uploading || !!analyzingSample;

  return (
    <div className="glass-surface flex flex-col gap-1.5 p-2.5 rounded-2xl flex-1 min-h-0 overflow-hidden">
      <div className="text-xs font-semibold tracking-wider prism-title uppercase flex justify-between shrink-0">
        <span>APK Forensic Upload</span>
      </div>

      {!isRunning ? (
        <div className="flex flex-col gap-1.5 flex-1 min-h-0 overflow-hidden">
          {/* Manual upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".apk"
            onChange={handleApkUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={busy}
            className="prism-button w-full py-1.5 rounded-xl disabled:opacity-50 text-white text-[11px] font-semibold transition-all shrink-0"
          >
            {uploading ? 'Analyzing APK...' : 'Upload APK for Malware Analysis'}
          </button>

          {scenarioComplete && (
            <div className="glass-inset rounded-xl px-3 py-2 text-[10px] text-sky-200 leading-relaxed shrink-0">
              Previous report is ready. Upload another APK or select a sample below.
            </div>
          )}

          {/* Sample APK list */}
          <div className="flex flex-col gap-1.5 flex-1 min-h-0 overflow-hidden">
            <div className="flex items-center gap-2 shrink-0 pt-1">
              <div className="h-px flex-1 bg-white/8" />
              <span className="text-[9px] text-zinc-500 uppercase tracking-widest whitespace-nowrap font-semibold">
                Test out these APKs
              </span>
              <div className="h-px flex-1 bg-white/8" />
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden pr-0.5 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent space-y-1">
              {SAMPLE_APKS.map((sample) => {
                const isActive = analyzingSample === sample.filename;
                return (
                  <button
                    key={sample.filename}
                    onClick={() => handleSampleClick(sample)}
                    disabled={busy}
                    className="w-full text-left rounded-lg px-2.5 py-1.5 border border-transparent bg-white/[0.02] hover:border-blue-500/20 hover:bg-blue-500/10 transition-all disabled:opacity-40 disabled:cursor-not-allowed group"
                  >
                    <span className="text-[10px] font-semibold text-zinc-200 group-hover:text-white transition-colors">
                      {isActive ? '⏳ ' : ''}{sample.label}
                    </span>
                    <p className="text-[9px] text-zinc-500 leading-snug mt-0.5">{sample.desc}</p>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-2 flex-1 min-h-0">
          <div className="glass-inset w-full px-3 py-2 rounded-xl text-sm text-zinc-400 italic text-center flex-1 min-h-[80px] flex items-center justify-center">
            Forensic scan running...
          </div>
          <button
            onClick={stop}
            className="black-button w-full py-2 rounded-xl text-white text-xs font-medium transition-colors shrink-0"
          >
            Stop
          </button>
        </div>
      )}
    </div>
  );
}
