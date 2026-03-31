import { useTranslation } from 'react-i18next';
import { NavLink } from 'react-router-dom';
import { useSettings } from '../../context/SettingsContext';
import {
  Home, Dna, Stethoscope, FileSearch, Settings, Menu, X, Sun, Moon, Languages,
} from 'lucide-react';
import { useState } from 'react';

const navItems = [
  { path: '/', icon: Home, labelKey: 'nav.home' },
  { path: '/hpo', icon: FileSearch, labelKey: 'nav.hpo_extraction' },
  { path: '/diagnosis', icon: Stethoscope, labelKey: 'nav.diagnosis' },
  { path: '/gene-diagnosis', icon: Dna, labelKey: 'nav.gene_diagnosis' },
  { path: '/settings', icon: Settings, labelKey: 'nav.settings' },
];

export default function Sidebar() {
  const { t, i18n } = useTranslation();
  const { settings, updateSettings } = useSettings();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleTheme = () => updateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' });
  const toggleLang = () => i18n.changeLanguage(i18n.language === 'en' ? 'es' : 'en');

  const sidebarContent = (
    <div className="flex flex-col h-full">
      {/* Logo */}
      <div className="p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center">
            <Dna className="w-6 h-6 text-white" />
          </div>
          {!collapsed && (
            <div>
              <h1 className="text-lg font-bold text-slate-900 dark:text-white">DeepRare</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">{t('app.subtitle')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {navItems.map(({ path, icon: Icon, labelKey }) => (
          <NavLink
            key={path}
            to={path}
            end={path === '/'}
            onClick={() => setMobileOpen(false)}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm font-medium ${
                isActive
                  ? 'bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                  : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'
              }`
            }
          >
            <Icon className="w-5 h-5 shrink-0" />
            {!collapsed && <span>{t(labelKey)}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Bottom controls */}
      <div className="p-3 border-t border-slate-200 dark:border-slate-700 space-y-2">
        <button onClick={toggleLang}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 w-full">
          <Languages className="w-5 h-5" />
          {!collapsed && <span>{i18n.language === 'en' ? 'Español' : 'English'}</span>}
        </button>
        <button onClick={toggleTheme}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 w-full">
          {settings.theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          {!collapsed && <span>{settings.theme === 'dark' ? t('settings.theme_light') : t('settings.theme_dark')}</span>}
        </button>
        <button onClick={() => setCollapsed(!collapsed)}
          className="hidden lg:flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800 w-full">
          <Menu className="w-5 h-5" />
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile toggle */}
      <button onClick={() => setMobileOpen(true)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 bg-white dark:bg-slate-800 rounded-lg shadow-lg">
        <Menu className="w-5 h-5 text-slate-700 dark:text-slate-300" />
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40 bg-black/50" onClick={() => setMobileOpen(false)}>
          <div className="w-64 h-full bg-white dark:bg-slate-900 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <button onClick={() => setMobileOpen(false)} className="absolute top-4 right-4">
              <X className="w-5 h-5 text-slate-500" />
            </button>
            {sidebarContent}
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <aside className={`hidden lg:flex flex-col ${collapsed ? 'w-20' : 'w-64'} h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700 transition-all duration-300 shrink-0`}>
        {sidebarContent}
      </aside>
    </>
  );
}
