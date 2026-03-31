import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronUp, Dna } from 'lucide-react';
import { Badge } from '../ui/Components';

function ImpactBadge({ impact }) {
  const variants = {
    HIGH: 'danger',
    MODERATE: 'warning',
    LOW: 'info',
    MODIFIER: 'default',
  };
  return <Badge variant={variants[impact] || 'default'}>{impact}</Badge>;
}

function PathogenicityBar({ score }) {
  const pct = Math.min(score * 100, 100);
  const color =
    pct >= 70 ? 'bg-red-500' : pct >= 40 ? 'bg-amber-500' : 'bg-green-500';
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-600 dark:text-slate-400">{score}</span>
    </div>
  );
}

export default function MutationPanel({ mutationDetails, variantData }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const [showAll, setShowAll] = useState(false);

  if (!mutationDetails && (!variantData || variantData.length === 0)) return null;

  const hasTable = variantData && variantData.length > 0;
  const displayed = showAll ? variantData : (variantData || []).slice(0, 10);

  return (
    <div className="border border-slate-200 dark:border-slate-700 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-3 px-4 py-3 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
      >
        <Dna className="w-4 h-4 text-purple-500" />
        <span className="flex-1 text-left">{t('gene.mutation_title')}</span>
        {hasTable && (
          <span className="text-xs text-slate-500 mr-2">
            {variantData.length} {t('gene.variants_found')}
          </span>
        )}
        {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {expanded && (
        <div className="border-t border-slate-200 dark:border-slate-700">
          {/* Summary text */}
          {mutationDetails && (
            <div className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400 whitespace-pre-wrap bg-slate-50/50 dark:bg-slate-800/30">
              {mutationDetails}
            </div>
          )}

          {/* Variant table */}
          {hasTable && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_gene')}</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_position')}</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_change')}</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_consequence')}</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_impact')}</th>
                    <th className="px-3 py-2 text-left font-medium">SIFT</th>
                    <th className="px-3 py-2 text-left font-medium">PolyPhen</th>
                    <th className="px-3 py-2 text-left font-medium">ClinVar</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_freq')}</th>
                    <th className="px-3 py-2 text-left font-medium">{t('gene.col_pathogenicity')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {displayed.map((v, i) => (
                    <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                      <td className="px-3 py-2 font-medium text-blue-600 dark:text-blue-400">
                        {v.gene || '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400 font-mono">
                        chr{v.chrom}:{v.pos}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400 font-mono">
                        {v.ref}&gt;{v.alt}
                        {v.genotype && (
                          <span className="ml-1 text-slate-400">({v.genotype})</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400 max-w-[180px] truncate" title={v.consequence}>
                        {v.consequence || '—'}
                        {v.hgvsp && (
                          <div className="text-[10px] text-slate-400 truncate" title={v.hgvsp}>
                            {v.hgvsp}
                          </div>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <ImpactBadge impact={v.impact || 'MODIFIER'} />
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {v.sift || '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {v.polyphen || '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400">
                        {v.clinvar || 'N/A'}
                      </td>
                      <td className="px-3 py-2 text-slate-600 dark:text-slate-400 font-mono">
                        {v.pop_freq !== undefined ? v.pop_freq.toFixed(6) : '—'}
                      </td>
                      <td className="px-3 py-2">
                        <PathogenicityBar score={v.pathogenicity_score || 0} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {variantData.length > 10 && (
                <div className="px-4 py-2 text-center">
                  <button
                    onClick={() => setShowAll(!showAll)}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
                  >
                    {showAll
                      ? t('gene.show_less')
                      : t('gene.show_all', { count: variantData.length })}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
