import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, Globe, Users, Brain, Sparkles } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = false, markdown = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        {Icon && <Icon className="w-4 h-4" />}
        <span className="flex-1 text-left">{title}</span>
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>
      {open && (
        <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 text-sm text-slate-600 dark:text-slate-400">
          {markdown ? (
            <div className="prose prose-sm prose-slate dark:prose-invert max-w-none
              prose-headings:text-slate-800 dark:prose-headings:text-slate-200
              prose-h2:text-base prose-h2:font-bold prose-h2:mt-4 prose-h2:mb-2 prose-h2:border-b prose-h2:border-slate-200 dark:prose-h2:border-slate-700 prose-h2:pb-1
              prose-h3:text-sm prose-h3:font-semibold prose-h3:mt-3 prose-h3:mb-1
              prose-p:my-1 prose-ul:my-1 prose-li:my-0.5
              prose-strong:text-blue-700 dark:prose-strong:text-blue-400">
              <ReactMarkdown>{children}</ReactMarkdown>
            </div>
          ) : (
            <div className="whitespace-pre-wrap">{children}</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function EvidencePanel({ webEvidence, similarCases, reflection, finalDiagnosis }) {
  const { t } = useTranslation();

  const hasReflection = reflection && typeof reflection === 'string' && reflection.trim().length > 0;

  return (
    <div className="space-y-3">
      {finalDiagnosis && (
        <CollapsibleSection title={t('diagnosis.final_diagnosis')} icon={Brain} defaultOpen markdown>
          {finalDiagnosis}
        </CollapsibleSection>
      )}
      {hasReflection && (
        <CollapsibleSection title={t('diagnosis.reflection')} icon={Sparkles} defaultOpen markdown>
          {reflection}
        </CollapsibleSection>
      )}
      {webEvidence && (
        <CollapsibleSection title={t('diagnosis.web_evidence')} icon={Globe} markdown>
          {webEvidence}
        </CollapsibleSection>
      )}
      {similarCases && similarCases.length > 0 && (
        <CollapsibleSection title={t('diagnosis.similar_cases')} icon={Users}>
          {similarCases.map((c, i) => (
            <div key={i} className="mb-2 p-2 bg-slate-50 dark:bg-slate-800 rounded text-xs">
              {typeof c === 'string' ? c : JSON.stringify(c, null, 2)}
            </div>
          ))}
        </CollapsibleSection>
      )}
    </div>
  );
}
