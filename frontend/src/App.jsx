import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Header from "./components/Layout/Header";
import TabBar from "./components/Layout/TabBar";
import EnterpriseChat from "./components/Chat/EnterpriseChat";
import DockerPhysicsMonitor from "./components/Monitor/DockerPhysicsMonitor";
import CommandPrompt from "./components/Chat/CommandPrompt";
import CausalDAG from "./components/CausalGraph/CausalDAG";
import DeadTimeline from "./components/Counterfactual/DeadTimeline";
import GitRCAPanel from "./components/GitPanel/GitRCAPanel";
import RewardCurve from "./components/Training/RewardCurve";
import BeforeAfterSplit from "./components/Training/BeforeAfterSplit";
import RewardMathFeed from "./components/Training/RewardMathFeed";
import FinOpsPreFlightAudit from "./components/Training/FinOpsPreFlightAudit";
import { useSimulationState } from "./store/simulationStore";

const THREAT_COLOR = {
  BENIGN: 'text-sky-300', LOW: 'text-sky-300',
  MEDIUM: 'text-amber-400', HIGH: 'text-red-400', CRITICAL: 'text-red-300',
};

function Metric({ label, children }) {
  return (
    <span className="text-zinc-500">
      {label}: <span className="forensic-token text-zinc-200">{children}</span>
    </span>
  );
}

function FinOpsSummaryBar() {
  const {
    messages, scenarioComplete, rewardFeed, verdict,
    apkPermissionCount, fileSizeBytes,
  } = useSimulationState();
  if (messages.length === 0) return null;

  const steps = rewardFeed.length;
  const level = verdict ? String(verdict.threat_level || '').replace('THREAT_', '') : (scenarioComplete ? '—' : 'ANALYZING');
  const levelClass = THREAT_COLOR[level] || 'text-zinc-400';
  const sizeBytes = Number(fileSizeBytes) || 0;
  const sizeLabel = sizeBytes <= 0 ? '—'
    : sizeBytes < 1024 * 1024 ? `${(sizeBytes / 1024).toFixed(1)} KB`
    : `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;

  return (
    <div className="shrink-0 rounded-2xl glass-surface px-4 py-3 transition-colors">
      <div className="flex items-center gap-3 mb-2">
        <span className={`w-1.5 h-1.5 rounded-full ${scenarioComplete ? 'bg-sky-300' : 'bg-violet-300 animate-pulse'}`} />
        <span className="prism-title font-display text-[11px] font-semibold tracking-wide">
          VaultAgent Analysis Summary
        </span>
        <span className="text-[9px] forensic-token text-zinc-500">
          {scenarioComplete ? '[ REPORT READY ]' : '[ ANALYZING ]'}
        </span>
      </div>
      <div className="flex items-center gap-x-5 gap-y-1.5 text-[10px] flex-wrap">
        <Metric label="Target">1 APK · {sizeLabel}</Metric>
        <Metric label="Permissions">{apkPermissionCount || 0}</Metric>
        <Metric label="Pipeline Steps">{steps}</Metric>
        <span className="text-zinc-500">Threat Level: <span className={`forensic-token font-bold ${levelClass}`}>{level}</span></span>
        {verdict && (
          <>
            <Metric label="Score">{verdict.threat_score}/100</Metric>
            <Metric label="Family">{verdict.malware_family}</Metric>
            <Metric label="Indicators">{verdict.indicators?.length || 0}</Metric>
          </>
        )}
        <span className="text-zinc-500">Data Exfiltration Risk: <span className="forensic-token text-sky-300 font-bold">ZERO</span> <span className="text-zinc-600">(Air-Gapped)</span></span>
      </div>
    </div>
  );
}

export default function App() {
  const [activeTab, setActiveTab] = useState("live");
  const { isRunning, scenarioComplete } = useSimulationState();

  // Direct route detection for isolated dashboard views
  const isTrainingPage = window.location.pathname === "/training-proof";

  const TrainingGrid = () => (
    <div className="h-full w-full overflow-y-auto overflow-x-hidden pr-1 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
      <div
        className="h-full min-h-[560px] p-2 gap-3 grid text-zinc-300"
        style={{
          gridTemplateColumns: "minmax(0, 1.35fr) minmax(280px, 0.75fr)",
          gridTemplateRows: "minmax(240px, 0.9fr) minmax(260px, 1fr)",
        }}
      >
        {/* Top-left: Reward trace */}
        <div className="min-w-0 min-h-0">
          <RewardCurve />
        </div>

        {/* Top-right: Reward feed */}
        <div className="min-w-0 min-h-0">
          <RewardMathFeed />
        </div>

        {/* Bottom-left: Incident phases */}
        <div className="min-w-0 min-h-0">
          <BeforeAfterSplit />
        </div>

        {/* Bottom-right: FinOps gatekeeper */}
        <div className="min-w-0 min-h-0">
          <FinOpsPreFlightAudit />
        </div>
      </div>
    </div>
  );

  if (isTrainingPage) {
    return (
      <div className="h-screen w-screen overflow-hidden">
        <TrainingGrid />
      </div>
    );
  }

  return (
    <div className="dashboard-shell flex flex-col min-h-screen lg:h-screen text-zinc-300 relative overflow-hidden lg:overflow-hidden">
      <Header />
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="relative z-10 flex-1 min-h-0 overflow-auto lg:overflow-hidden">
        <AnimatePresence mode="wait">
          {activeTab === "live" && (
            <motion.div
              key="live"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.2 }}
              className="min-h-full lg:h-full p-2 sm:p-3 flex flex-col gap-3"
            >
              <div className="flex-1 min-h-0 flex flex-col xl:flex-row gap-3 overflow-visible lg:overflow-hidden">
                <div className="w-full xl:w-[320px] 2xl:w-[340px] shrink-0 flex flex-col gap-3 min-h-0">
                  <div className="shrink-0">
                    <DockerPhysicsMonitor />
                  </div>
                  {/* Upload & sample selector — fills remaining space with internal scroll */}
                  <div className="flex-1 min-h-0 flex flex-col">
                    <CommandPrompt />
                  </div>
                </div>

                <div className="flex-1 flex flex-col min-w-0 min-h-[560px] xl:min-h-0 overflow-hidden">
                  <div className="flex-1 min-h-0 overflow-hidden">
                    <EnterpriseChat />
                  </div>
                </div>

                <div className="w-full xl:w-[430px] 2xl:w-[460px] shrink-0 flex flex-col gap-3 min-h-0 overflow-visible xl:overflow-y-auto overscroll-contain scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent xl:pr-1">
                  <div className="shrink-0">
                    <GitRCAPanel />
                  </div>
                  <div className="shrink-0">
                    <DeadTimeline />
                  </div>
                </div>
              </div>

              {/* VaultAgent ingestion summary - full-width bar at the bottom */}
              <FinOpsSummaryBar />
            </motion.div>
          )}

          {activeTab === "graph" && (
            <motion.div
              key="graph"
              initial={{ opacity: 0, scale: 0.99 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.99 }}
              transition={{ duration: 0.2 }}
              className="h-full p-2 sm:p-3"
            >
              <div className="h-full w-full overflow-hidden">
                <CausalDAG />
              </div>
            </motion.div>
          )}

          {activeTab === "training" && (
            <motion.div
              key="training"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="h-full max-h-full overflow-auto min-h-0 p-2 sm:p-3"
            >
              <TrainingGrid />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
