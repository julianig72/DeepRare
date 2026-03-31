import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { Download, ArrowRight } from 'lucide-react';
import { Button, Card, CardHeader, CardBody, TextArea } from '../components/ui/Components';
import { extractHPO } from '../services/api';
import { useSettings } from '../context/SettingsContext';

export default function HPOExtractionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { settings } = useSettings();
  const [text, setText] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleExtract = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setError('');
    try {
      const data = await extractHPO(text, settings.keys.openai);
      setResults(data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  const exportCSV = () => {
    if (!results?.phenotypes?.length) return;
    const header = 'Phenotype,HPO Code,Description,Similarity\n';
    const rows = results.phenotypes.map(p =>
      `"${p.phenotype_text}","${p.hpo_code}","${p.hpo_description}",${p.similarity}`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'hpo_extraction.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const useForDiagnosis = () => {
    if (!results?.phenotypes?.length) return;
    const phenotypes = results.phenotypes.map(p => p.phenotype_text).join(', ');
    const hpoIds = results.phenotypes.filter(p => p.hpo_code).map(p => p.hpo_code).join(', ');
    navigate('/diagnosis', { state: { phenotypes, hpoIds, clinicalText: text } });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{t('hpo.title')}</h2>
        <p className="text-slate-600 dark:text-slate-400 mt-1">{t('hpo.description')}</p>
      </div>

      <Card>
        <CardBody>
          <TextArea
            label={t('hpo.input_label')}
            placeholder={t('hpo.input_placeholder')}
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={8}
          />
          <div className="flex items-center gap-3 mt-4">
            <Button onClick={handleExtract} loading={loading} disabled={!text.trim()}>
              {loading ? t('hpo.extracting') : t('hpo.extract_btn')}
            </Button>
            {text && (
              <Button variant="ghost" onClick={() => { setText(''); setResults(null); setError(''); }}>
                {t('common.clear')}
              </Button>
            )}
          </div>
          {error && <p className="mt-3 text-sm text-red-500">{error}</p>}
        </CardBody>
      </Card>

      {results?.phenotypes?.length > 0 && (
        <Card>
          <CardHeader className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t('hpo.results_title')}</h3>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={exportCSV}>
                <Download className="w-4 h-4" /> {t('hpo.export_csv')}
              </Button>
              <Button variant="success" onClick={useForDiagnosis}>
                {t('hpo.use_for_diagnosis')} <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800">
                <tr>
                  <th className="px-6 py-3 text-left font-medium text-slate-600 dark:text-slate-400">{t('hpo.col_phenotype')}</th>
                  <th className="px-6 py-3 text-left font-medium text-slate-600 dark:text-slate-400">{t('hpo.col_hpo_code')}</th>
                  <th className="px-6 py-3 text-left font-medium text-slate-600 dark:text-slate-400">{t('hpo.col_hpo_desc')}</th>
                  <th className="px-6 py-3 text-right font-medium text-slate-600 dark:text-slate-400">{t('hpo.col_similarity')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                {results.phenotypes.map((p, i) => (
                  <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                    <td className="px-6 py-3 text-slate-900 dark:text-white font-medium">{p.phenotype_text}</td>
                    <td className="px-6 py-3">
                      {p.hpo_code ? (
                        <a href={`https://hpo.jax.org/browse/term/${p.hpo_code}`} target="_blank" rel="noopener noreferrer"
                          className="text-blue-600 hover:underline">{p.hpo_code}</a>
                      ) : '—'}
                    </td>
                    <td className="px-6 py-3 text-slate-600 dark:text-slate-400">{p.hpo_description || '—'}</td>
                    <td className="px-6 py-3 text-right">
                      <span className={`font-mono ${p.similarity >= 0.8 ? 'text-emerald-600' : p.similarity >= 0.5 ? 'text-amber-600' : 'text-slate-500'}`}>
                        {(p.similarity * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
