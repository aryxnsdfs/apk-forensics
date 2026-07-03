import { motion } from 'framer-motion';

const TABS = [
  { id: 'live', label: 'Live Environment' },
  { id: 'graph', label: 'Attack Graph' },
  { id: 'training', label: 'Execution Evidence' },
];

export default function TabBar({ activeTab, onTabChange }) {
  return (
    <div className="relative z-10 flex items-center gap-1 px-3 sm:px-4 py-2 glass-surface border-x-0 border-t-0 rounded-none shrink-0 overflow-x-auto">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`relative px-4 py-2 text-xs font-medium rounded-xl transition-colors shrink-0 ${
            activeTab === tab.id
              ? 'text-white'
              : 'text-zinc-500 hover:text-zinc-200'
          }`}
        >
          <span className="relative z-10 flex items-center gap-1.5">
            {tab.label}
          </span>
          {activeTab === tab.id && (
            <motion.div
              layoutId="tab-indicator"
              className="absolute inset-0 prism-button rounded-xl"
              style={{ zIndex: 0 }}
              transition={{ type: 'spring', stiffness: 500, damping: 35 }}
            />
          )}
        </button>
      ))}
    </div>
  );
}
