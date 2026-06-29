import { useState, useRef } from 'react';
import { useSimulation } from '../../hooks/useSimulation';
import { useSimulationState, getApiBase } from '../../store/simulationStore';

export default function CommandPrompt() {
  const { isRunning, scenarioComplete } = useSimulationState();
  const { stop } = useSimulation();
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleApkUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
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

  return (
    <div className="flex flex-col gap-2 p-3 bg-zinc-900 border border-zinc-800 rounded-lg flex-1 min-h-0 overflow-y-auto scrollbar-thin scrollbar-thumb-zinc-700">
      <div className="text-xs font-semibold tracking-wider text-zinc-500 uppercase flex justify-between shrink-0">
        <span>APK Forensic Upload</span>
      </div>

      {!isRunning ? (
        <div className="flex flex-col gap-2 flex-1 min-h-0">
          <div className="rounded-md border border-zinc-800 bg-zinc-950/70 px-3 py-2 text-[10px] text-zinc-400 leading-relaxed shrink-0">
            Upload an Android APK packet to execute the offline multi-agent forensic scanning pipeline.
          </div>
          {scenarioComplete && (
            <div className="rounded-md border border-emerald-900/40 bg-emerald-950/10 px-3 py-2 text-[10px] text-emerald-300 leading-relaxed shrink-0">
              Previous scan completed. Upload another APK to start a new forensic run.
            </div>
          )}

          {/* VaultAgent — offline APK forensic upload */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".apk"
            onChange={handleApkUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full py-2.5 rounded-md bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-sm font-semibold transition-colors shrink-0"
          >
            {uploading ? 'Analyzing APK…' : '⬆ Upload APK for Malware Analysis'}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2 flex-1 min-h-0">
          <div className="w-full px-3 py-2 rounded-md bg-zinc-950 border border-zinc-700 text-sm text-zinc-500 italic text-center flex-1 min-h-[80px] flex items-center justify-center">
            Forensic scan running…
          </div>
          <button
            onClick={stop}
            className="w-full py-1.5 rounded-md bg-red-600 hover:bg-red-500 text-white text-xs font-medium transition-colors shrink-0"
          >
            Stop
          </button>
        </div>
      )}
    </div>
  );
}
