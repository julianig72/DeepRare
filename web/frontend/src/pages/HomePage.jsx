import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { FileSearch, Stethoscope, Dna, ArrowRight, Settings } from 'lucide-react';
import { Button, Card, CardBody } from '../components/ui/Components';

const features = [
  { key: 'hpo', icon: FileSearch, path: '/hpo', color: 'from-emerald-500 to-teal-600' },
  { key: 'diagnosis', icon: Stethoscope, path: '/diagnosis', color: 'from-blue-500 to-indigo-600' },
  { key: 'gene', icon: Dna, path: '/gene-diagnosis', color: 'from-purple-500 to-violet-600' },
];

export default function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="text-center py-12">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600 to-purple-600 mb-6">
          <Dna className="w-10 h-10 text-white" />
        </div>
        <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-4">{t('home.welcome')}</h1>
        <p className="text-lg text-slate-600 dark:text-slate-400 max-w-2xl mx-auto">{t('home.description')}</p>
        <div className="flex items-center justify-center gap-4 mt-8">
          <Button onClick={() => navigate('/hpo')}>
            {t('home.get_started')} <ArrowRight className="w-4 h-4" />
          </Button>
          <Button variant="secondary" onClick={() => navigate('/settings')}>
            <Settings className="w-4 h-4" /> {t('home.configure_keys')}
          </Button>
        </div>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {features.map(({ key, icon: Icon, path, color }) => (
          <Card key={key} className="cursor-pointer hover:shadow-md transition-shadow" onClick={() => navigate(path)}>
            <CardBody className="text-center py-8">
              <div className={`inline-flex items-center justify-center w-14 h-14 rounded-xl bg-gradient-to-br ${color} mb-4`}>
                <Icon className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-2">{t(`home.feature_${key}`)}</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">{t(`home.feature_${key}_desc`)}</p>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
