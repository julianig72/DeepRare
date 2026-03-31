import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '../ui/Components';

export default function DiseaseCard({ rank, disease_name, orphanet_id, confidence, evidence_summary }) {
  const [expanded, setExpanded] = useState(rank <= 3);

  const medalColors = {
    1: 'from-yellow-400 to-amber-500',
    2: 'from-slate-300 to-slate-400',
    3: 'from-amber-600 to-amber-700',
  };

  return (
    <div className="rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-4 p-4 text-left"
      >
        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 bg-gradient-to-br ${
          medalColors[rank] || 'from-slate-500 to-slate-600'
        }`}>
          #{rank}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-slate-900 dark:text-white">{disease_name}</h4>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            {orphanet_id && <Badge variant="info">ORPHA:{orphanet_id}</Badge>}
            {confidence && <Badge variant="success">{confidence}</Badge>}
          </div>
        </div>
        {evidence_summary && (
          expanded
            ? <ChevronUp className="w-4 h-4 text-slate-400 shrink-0 mt-1" />
            : <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 mt-1" />
        )}
      </button>
      {evidence_summary && expanded && (
        <div className="px-4 pb-4 pl-[4.5rem]">
          <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed whitespace-pre-wrap bg-slate-50 dark:bg-slate-800/50 rounded p-3 border-l-2 border-blue-400">
            <span className="font-medium text-blue-600 dark:text-blue-400 block mb-1">Clinical Reasoning:</span>
            {evidence_summary}
          </div>
        </div>
      )}
    </div>
  );
}
