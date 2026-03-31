import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { Button, Card, CardHeader, CardBody, TextArea, Input, Select, ProgressSteps } from '../components/ui/Components';
import DiseaseCard from '../components/diagnosis/DiseaseCard';
import EvidencePanel from '../components/diagnosis/EvidencePanel';
import { streamDiagnosis, fetchModels } from '../services/api';
import { useSettings } from '../context/SettingsContext';

export default function DiagnosisPage() {
  const { t } = useTranslation();
  const location = useLocation();
  const { settings } = useSettings();

  const [models, setModels] = useState([]);
  const [form, setForm] = useState({
    clinicalText: '',
    phenotypes: '',
    hpoIds: '',
    model: settings.model || 'gpt-4o',
    searchEngine: 'duckduckgo',
  });
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [cancelFn, setCancelFn] = useState(null);

  useEffect(() => {
    fetchModels().then(setModels).catch(() => {});
  }, []);

  useEffect(() => {
    if (location.state) {
      setForm(prev => ({
        ...prev,
        clinicalText: location.state.clinicalText || prev.clinicalText,
        phenotypes: location.state.phenotypes || prev.phenotypes,
        hpoIds: location.state.hpoIds || prev.hpoIds,
      }));
    }
  }, [location.state]);

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

    const cancel = streamDiagnosis(
      {
        clinicalText: form.clinicalText,
        phenotypes: form.phenotypes.split(',').map(s => s.trim()).filter(Boolean),
        phenotypeIds: form.hpoIds.split(',').map(s => s.trim()).filter(Boolean),
        model: form.model,
        searchEngine: form.searchEngine,
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
        if (event.step === 'complete' && event.data) {
          setResult(event.data);
        }
        if (event.step === 'error') {
          setError(event.detail);
        }
      },
      (err) => setError(err.message),
      () => setRunning(false),
    );

    setCancelFn(() => cancel);
  }, [form, t]);

  const handleCancel = () => {
    cancelFn?.();
    setRunning(false);
  };

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
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{t('diagnosis.title')}</h2>
        <p className="text-slate-600 dark:text-slate-400 mt-1">{t('diagnosis.description')}</p>
      </div>

      {/* Input form */}
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select
              label={t('diagnosis.model_label')}
              options={modelOptions}
              value={form.model}
              onChange={(e) => setForm(f => ({ ...f, model: e.target.value }))}
            />
            <Select
              label={t('diagnosis.search_label')}
              options={searchOptions}
              value={form.searchEngine}
              onChange={(e) => setForm(f => ({ ...f, searchEngine: e.target.value }))}
            />
          </div>
          <div className="flex gap-3">
            <Button onClick={handleDiagnose} loading={running}
              disabled={!form.clinicalText.trim() && !form.phenotypes.trim()}>
              {running ? t('diagnosis.diagnosing') : t('diagnosis.diagnose_btn')}
            </Button>
            {running && (
              <Button variant="danger" onClick={handleCancel}>{t('common.cancel')}</Button>
            )}
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
        </CardBody>
      </Card>

      {/* Progress */}
      {steps.length > 0 && running && (
        <Card>
          <CardBody>
            <ProgressSteps steps={steps} />
          </CardBody>
        </Card>
      )}

      {/* Results */}
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
