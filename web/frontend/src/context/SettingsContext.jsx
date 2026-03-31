import { createContext, useContext, useState, useEffect } from 'react';

const SettingsContext = createContext(null);

const DEFAULT_SETTINGS = {
  keys: { openai: '', anthropic: '', google: '', deepseek: '' },
  model: 'gpt-4o',
  searchEngine: 'duckduckgo',
  theme: 'light',
};

export function SettingsProvider({ children }) {
  const [settings, setSettings] = useState(() => {
    try {
      const stored = localStorage.getItem('deeprare_settings');
      const keys = JSON.parse(localStorage.getItem('deeprare_keys') || '{}');
      const parsed = stored ? JSON.parse(stored) : {};
      return { ...DEFAULT_SETTINGS, ...parsed, keys: { ...DEFAULT_SETTINGS.keys, ...keys } };
    } catch {
      return DEFAULT_SETTINGS;
    }
  });

  useEffect(() => {
    localStorage.setItem('deeprare_settings', JSON.stringify(settings));
    localStorage.setItem('deeprare_keys', JSON.stringify(settings.keys));
    localStorage.setItem('deeprare_model', settings.model);
    document.documentElement.classList.toggle('dark', settings.theme === 'dark');
  }, [settings]);

  const updateSettings = (updates) => setSettings((prev) => ({ ...prev, ...updates }));
  const updateKey = (provider, value) =>
    setSettings((prev) => ({ ...prev, keys: { ...prev.keys, [provider]: value } }));

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, updateKey }}>
      {children}
    </SettingsContext.Provider>
  );
}

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}
