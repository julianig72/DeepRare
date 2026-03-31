import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { Upload } from 'lucide-react';
import { Button, Card, CardHeader, CardBody, TextArea, Input, Select, ProgressSteps } from '../components/ui/Components';
import DiseaseCard from '../components/diagnosis/DiseaseCard';
import EvidencePanel from '../components/diagnosis/EvidencePanel';
import MutationPanel from '../components/diagnosis/MutationPanel';
import { streamGeneDiagnosis, fetchModels } from '../services/api';
import { useSettings } from '../context/SettingsContext';

export default function GeneDiagnosisPage() {
  const { t } = useTranslation();
  const { settings } = useSettings();
  const [models, setModels] = useState([]);
  const [form, setForm] = useState({
    clinicalText: '',
    phenotypes: '',
    hpoIds: '',
    model: settings.model || 'gpt-4o',
    searchEngine: 'duckduckgo',
  });
  const [vcfFile, setVcfFile] = useState(null);
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [cancelFn, setCancelFn] = useState(null);

  useEffect(() => {
    fetchModels().then(setModels).catch(() => {});
  }, []);

  const handleDiagnose = useCallback(() => {
    setRunning(true);
    setError('');
    setResult(null);
    setSteps([
      { label: t('diagnosis.step_init'), status: 'pending' },
      { label: t('diagnosis.step_diagnosis'), status: 'pending' },
      { label: t('diagnosis.step_complete'), status: 'pending' },
    ]);

    const stepMap = { initialization: 0, diagnosis: 1, complete: 2 };

    const cancel = streamGeneDiagnosis(
      {
        clinicalText: form.clinicalText,
        phenotypes: form.phenotypes.split(',').map(s => s.trim()).filter(Boolean),
        phenotypeIds: form.hpoIds.split(',').map(s => s.trim()).filter(Boolean),
        model: form.model,
        searchEngine: form.searchEngine,
        vcfFile,
      },
      (event) => {
        const idx = stepMap[event.step];
        if (idx !== undefined) {
          setSteps(prev => prev.map((s, i) => {
            if (i === idx) return { ...s, status: event.status, detail: event.detail };
            if (i < idx && s.status !== 'completed') return { ...s, status: 'completed' };
            return s;
          }));
        }
        if (event.step === 'complete' && event.data) setResult(event.data);
        if (event.step === 'error') setError(event.detail);
      },
      (err) => setError(err.message),
      () => setRunning(false),
    );
    setCancelFn(() => cancel);
  }, [form, vcfFile, t]);

  const modelOptions = models.map(m => ({ value: m.id, label: `${m.name} (${m.provider})` }));
  if (!modelOptions.length) modelOptions.push({ value: 'gpt-4o', label: 'GPT-4o (openai)' });

  const searchOptions = [
    { value: 'duckduckgo', label: 'DuckDuckGo' },
    { value: 'google', label: 'Google' },
    { value: 'bing', label: 'Bing' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{t('gene.title')}</h2>
        <p className="text-slate-600 dark:text-slate-400 mt-1">{t('gene.description')}</p>
      </div>

      <Card>
        <CardBody className="space-y-4">
          <TextArea
            label={t('diagnosis.clinical_text_label')}
            placeholder={t('diagnosis.clinical_text_placeholder')}
            value={form.clinicalText}
            onChange={(e) => setForm(f => ({ ...f, clinicalText: e.target.value }))}
            rows={5}
          />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label={t('diagnosis.phenotypes_label')}
              placeholder={t('diagnosis.phenotypes_placeholder')}
              value={form.phenotypes}
              onChange={(e) => setForm(f => ({ ...f, phenotypes: e.target.value }))}
            />
            <Input
              label={t('diagnosis.hpo_ids_label')}
              placeholder={t('diagnosis.hpo_ids_placeholder')}
              value={form.hpoIds}
              onChange={(e) => setForm(f => ({ ...f, hpoIds: e.target.value }))}
            />
          </div>

          {/* VCF Upload */}
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{t('gene.vcf_label')}</label>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 px-4 py-2.5 rounded-lg border-2 border-dashed border-slate-300 dark:border-slate-600 hover:border-blue-500 dark:hover:border-blue-500 cursor-pointer transition-colors">
                <Upload className="w-5 h-5 text-slate-500" />
                <span className="text-sm text-slate-600 dark:text-slate-400">
                  {vcfFile ? vcfFile.name : t('gene.upload_vcf')}
                </span>
                <input type="file" accept=".vcf,.vcf.gz" className="hidden"
                  onChange={(e) => setVcfFile(e.target.files?.[0] || null)} />
              </label>
              {vcfFile && (
                <Button variant="ghost" onClick={() => setVcfFile(null)}>{t('common.clear')}</Button>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select label={t('diagnosis.model_label')} options={modelOptions}
              value={form.model} onChange={(e) => setForm(f => ({ ...f, model: e.target.value }))} />
            <Select label={t('diagnosis.search_label')} options={searchOptions}
              value={form.searchEngine} onChange={(e) => setForm(f => ({ ...f, searchEngine: e.target.value }))} />
          </div>

          <div className="flex gap-3">
            <Button onClick={handleDiagnose} loading={running}
              disabled={!form.clinicalText.trim() && !form.phenotypes.trim() && !vcfFile}>
              {running ? t('diagnosis.diagnosing') : t('diagnosis.diagnose_btn')}
            </Button>
            {running && (
              <Button variant="danger" onClick={() => { cancelFn?.(); setRunning(false); }}>
                {t('common.cancel')}
              </Button>
            )}
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
        </CardBody>
      </Card>

      {steps.length > 0 && running && (
        <Card><CardBody><ProgressSteps steps={steps} /></CardBody></Card>
      )}

      {result && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t('diagnosis.results_title')}</h3>
            </CardHeader>
            <CardBody className="space-y-3">
              {result.diseases?.length > 0 ? (
                result.diseases.map((d, i) => <DiseaseCard key={i} {...d} />)
              ) : (
                <p className="text-sm text-slate-500">{t('diagnosis.no_results')}</p>
              )}
            </CardBody>
          </Card>

          {(result.mutation_details || (result.variant_data && result.variant_data.length > 0)) && (
            <MutationPanel
              mutationDetails={result.mutation_details}
              variantData={result.variant_data}
            />
          )}

          <EvidencePanel
            webEvidence={result.web_evidence}
            similarCases={result.similar_cases}
            reflection={result.reflection}
            finalDiagnosis={result.final_diagnosis}
          />
        </div>
      )}
    </div>
  );
}
