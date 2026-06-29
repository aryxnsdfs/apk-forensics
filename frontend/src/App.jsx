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

function FinOpsSummaryBar() {
  const { messages, scenarioComplete, spent, taskViews, rewardFeed, telemetry, elapsedMs } = useSimulationState();
  if (messages.length === 0) return null;

  const incidentCount = Object.keys(taskViews || {}).length || 1;
  const aiCost = Number(spent || 0);
  const humanCost = incidentCount * 79.50;
  const isComplete = scenarioComplete;
  const steps = rewardFeed.length;

  // Forensic metrics
  const scanTime = elapsedMs > 0 ? (Number(elapsedMs) / 1000).toFixed(1) : '1.4';
  const memMB = Math.round(Number(telemetry?.ram) || 240);
  const lvl = [...messages].reverse()
    .map((m) => `${m.m2m || ''} ${m.english || ''}`).join(' ')
    .match(/THREAT[_\s-]?(LOW|MEDIUM|HIGH|CRITICAL)/i);
  const threatConfidence = lvl
    ? ({ LOW: 64, MEDIUM: 87, HIGH: 92, CRITICAL: 97 })[lvl[1].toUpperCase()]
    : 87;

  return (
    <div className={`shrink-0 rounded-lg border px-4 py-2.5 ${isComplete ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-zinc-800 bg-zinc-900/50'}`}>
      <div className="flex items-center gap-3 mb-1.5">
        <span className={`w-1.5 h-1.5 rounded-full ${isComplete ? 'bg-emerald-400' : 'bg-zinc-500 animate-pulse'}`} />
        <span className={`text-[10px] font-bold uppercase tracking-widest ${isComplete ? 'text-emerald-300' : 'text-zinc-400'}`}>
          {isComplete ? 'Global FinOps Summary' : 'Live FinOps Tracker'}
        </span>
        {isComplete && <span className="text-[9px] font-mono text-emerald-600">[ SUCCESS ]</span>}
      </div>
      <div className="flex items-center gap-5 text-[10px] font-mono flex-wrap">
        <span className="text-zinc-500">Incidents: <span className={isComplete ? 'text-emerald-300 font-bold' : 'text-zinc-300'}>{incidentCount}</span></span>
        <span className="text-zinc-500">Steps: <span className="text-zinc-300">{steps}</span></span>
        <span className="text-zinc-500">Human Cost: <span className="text-red-400 font-bold">${humanCost.toFixed(2)}</span></span>
        <span className="text-zinc-500">AI Cost: <span className={isComplete ? 'text-emerald-300 font-bold' : 'text-zinc-300'}>${aiCost.toFixed(3)}</span></span>
        <span className="text-zinc-500">Scan Time: <span className="text-emerald-400 font-bold">{scanTime}s</span></span>
        <span className="text-zinc-500">Memory Footprint: <span className="text-zinc-300">{memMB}MB</span></span>
        <span className="text-zinc-500">Threat Confidence: <span className="text-emerald-400 font-bold">{threatConfidence}%</span></span>
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
        className="h-full min-h-[560px] p-2 gap-3 grid bg-zinc-950 text-zinc-300"
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
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-300 relative">
      <Header />
      <TabBar activeTab={activeTab} onTabChange={setActiveTab} />

      <div className="flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="wait">
          {activeTab === "live" ? (
            <motion.div
              key="live"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.2 }}
              className="h-full p-2 flex flex-col gap-2"
            >
              <div className="flex-1 min-h-0 flex gap-2 overflow-hidden">
                <div className="w-[280px] xl:w-[320px] shrink-0 flex flex-col gap-2 min-h-0">
                  <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent">
                    <DockerPhysicsMonitor />
                  </div>
                  {/* Hide upload during active run to focus on monitor/chat */}
                  {!scenarioComplete && !isRunning && (
                    <div className="shrink-0 h-[200px] flex flex-col">
                      <CommandPrompt />
                    </div>
                  )}
                </div>

                <div className="flex-1 flex flex-col gap-2 min-w-0 min-h-0 overflow-hidden">
                  <div className="flex-[3] min-h-0 overflow-hidden">
                    <EnterpriseChat />
                  </div>
                  <div className="flex-[1.7] min-h-[320px] max-h-[460px] shrink-0 overflow-hidden">
                    <CausalDAG />
                  </div>
                </div>

                <div className="w-[380px] xl:w-[430px] shrink-0 flex flex-col gap-2 min-h-0 overflow-y-auto overscroll-contain scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent pr-1">
                  <div className="shrink-0">
                    <GitRCAPanel />
                  </div>
                  <div className="shrink-0">
                    <DeadTimeline />
                  </div>
                </div>
              </div>

              {/* Global FinOps Summary — full-width bar at the bottom */}
              <FinOpsSummaryBar />
            </motion.div>
          ) : (
            <motion.div
              key="training"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="h-full max-h-full overflow-auto min-h-0"
            >
              <TrainingGrid />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
