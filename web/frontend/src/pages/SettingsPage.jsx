import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, X, Loader2, Eye, EyeOff } from 'lucide-react';
import { Button, Card, CardHeader, CardBody, Input, Select } from '../components/ui/Components';
import { useSettings } from '../context/SettingsContext';
import { validateKey, fetchModels } from '../services/api';

const providers = [
  { key: 'openai', labelKey: 'settings.openai_key', noteKey: 'settings.openai_note' },
  { key: 'anthropic', labelKey: 'settings.anthropic_key' },
  { key: 'google', labelKey: 'settings.google_key' },
  { key: 'deepseek', labelKey: 'settings.deepseek_key' },
];

export default function SettingsPage() {
  const { t, i18n } = useTranslation();
  const { settings, updateSettings, updateKey } = useSettings();
  const [models, setModels] = useState([]);
  const [validations, setValidations] = useState({});
  const [showKeys, setShowKeys] = useState({});
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchModels().then(setModels).catch(() => {});
  }, []);

  const handleValidate = async (provider) => {
    const key = settings.keys[provider];
    if (!key) return;
    setValidations(v => ({ ...v, [provider]: 'loading' }));
    try {
      const res = await validateKey(provider, key);
      setValidations(v => ({ ...v, [provider]: res.valid ? 'valid' : 'invalid' }));
    } catch {
      setValidations(v => ({ ...v, [provider]: 'invalid' }));
    }
  };

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const toggleShow = (key) => setShowKeys(s => ({ ...s, [key]: !s[key] }));

  const modelOptions = models.map(m => ({ value: m.id, label: `${m.name} (${m.provider})` }));
  if (!modelOptions.length) modelOptions.push({ value: 'gpt-4o', label: 'GPT-4o (openai)' });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 dark:text-white">{t('settings.title')}</h2>
        <p className="text-slate-600 dark:text-slate-400 mt-1">{t('settings.description')}</p>
      </div>

      {/* API Keys */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t('settings.api_keys')}</h3>
        </CardHeader>
        <CardBody className="space-y-4">
          {providers.map(({ key, labelKey, noteKey }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1.5">{t(labelKey)}</label>
              {noteKey && <p className="text-xs text-slate-500 mb-1.5">{t(noteKey)}</p>}
              <div className="flex items-center gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKeys[key] ? 'text' : 'password'}
                    value={settings.keys[key] || ''}
                    onChange={(e) => updateKey(key, e.target.value)}
                    placeholder={t('settings.key_placeholder')}
                    className="w-full px-3 py-2 pr-10 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 dark:text-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <button onClick={() => toggleShow(key)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    {showKeys[key] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <Button variant="secondary" onClick={() => handleValidate(key)} disabled={!settings.keys[key]}>
                  {validations[key] === 'loading' ? <Loader2 className="w-4 h-4 animate-spin" /> :
                   validations[key] === 'valid' ? <Check className="w-4 h-4 text-emerald-500" /> :
                   validations[key] === 'invalid' ? <X className="w-4 h-4 text-red-500" /> :
                   t('settings.validate_btn')}
                </Button>
              </div>
            </div>
          ))}
        </CardBody>
      </Card>

      {/* Preferences */}
      <Card>
        <CardHeader>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">{t('settings.default_model')}</h3>
        </CardHeader>
        <CardBody className="space-y-4">
          <Select
            label={t('settings.default_model')}
            options={modelOptions}
            value={settings.model}
            onChange={(e) => updateSettings({ model: e.target.value })}
          />
          <Select
            label={t('settings.language')}
            options={[
              { value: 'en', label: 'English' },
              { value: 'es', label: 'Español' },
            ]}
            value={i18n.language.startsWith('es') ? 'es' : 'en'}
            onChange={(e) => i18n.changeLanguage(e.target.value)}
          />
          <Select
            label={t('settings.theme')}
            options={[
              { value: 'light', label: t('settings.theme_light') },
              { value: 'dark', label: t('settings.theme_dark') },
            ]}
            value={settings.theme}
            onChange={(e) => updateSettings({ theme: e.target.value })}
          />
        </CardBody>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={handleSave}>{t('settings.save')}</Button>
        {saved && <span className="text-sm text-emerald-600 font-medium">{t('settings.saved')}</span>}
      </div>
    </div>
  );
}
