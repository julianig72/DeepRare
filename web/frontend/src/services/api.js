import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({ baseURL: API_BASE });

function getStoredKeys() {
  try {
    return JSON.parse(localStorage.getItem('deeprare_keys') || '{}');
  } catch { return {}; }
}

function getStoredModel() {
  return localStorage.getItem('deeprare_model') || 'gpt-4o';
}

function getProvider(modelId) {
  const providers = {
    'gpt-4o': 'openai', 'gpt-4o-mini': 'openai', 'o1': 'openai', 'o3-mini': 'openai',
    'claude-3-5-sonnet-20241022': 'anthropic', 'claude-3-5-haiku-20241022': 'anthropic',
    'gemini-2.0-flash': 'google', 'gemini-2.0-pro': 'google',
    'deepseek-v3-241226': 'deepseek', 'deepseek-r1-250120': 'deepseek',
  };
  return providers[modelId] || 'openai';
}

export async function fetchModels() {
  const res = await api.get('/config/models');
  return res.data.models;
}

export async function validateKey(provider, apiKey) {
  const res = await api.post('/config/validate-key', { provider, api_key: apiKey });
  return res.data;
}

export async function extractHPO(clinicalText, openaiKey) {
  const keys = getStoredKeys();
  const res = await api.post('/hpo/extract', {
    clinical_text: clinicalText,
    api_key: openaiKey || keys.openai || '',
  });
  return res.data;
}

export function streamDiagnosis(params, onEvent, onError, onComplete) {
  const keys = getStoredKeys();
  const model = params.model || getStoredModel();
  const provider = getProvider(model);

  const body = JSON.stringify({
    clinical_text: params.clinicalText || '',
    phenotypes: params.phenotypes || [],
    phenotype_ids: params.phenotypeIds || [],
    model,
    provider,
    api_key: params.apiKey || keys[provider] || '',
    openai_api_key: params.openaiKey || keys.openai || '',
    search_engine: params.searchEngine || 'duckduckgo',
  });

  const ctrl = new AbortController();

  fetch(`${API_BASE}/diagnosis/phenotype`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream' },
    body,
    signal: ctrl.signal,
  }).then(async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            onEvent(event);
            if (event.step === 'complete' || event.step === 'error') {
              onComplete?.(event);
            }
          } catch { /* ignore parse errors */ }
        }
      }
    }
    onComplete?.({ step: 'stream_end' });
  }).catch((err) => {
    if (err.name !== 'AbortError') onError?.(err);
  });

  return () => ctrl.abort();
}

export function streamGeneDiagnosis(params, onEvent, onError, onComplete) {
  const keys = getStoredKeys();
  const model = params.model || getStoredModel();
  const provider = getProvider(model);

  const formData = new FormData();
  formData.append('clinical_text', params.clinicalText || '');
  formData.append('phenotypes', (params.phenotypes || []).join(','));
  formData.append('phenotype_ids', (params.phenotypeIds || []).join(','));
  formData.append('model', model);
  formData.append('provider', provider);
  formData.append('api_key', params.apiKey || keys[provider] || '');
  formData.append('openai_api_key', params.openaiKey || keys.openai || '');
  formData.append('search_engine', params.searchEngine || 'duckduckgo');
  if (params.vcfFile) formData.append('vcf_file', params.vcfFile);

  const ctrl = new AbortController();

  fetch(`${API_BASE}/diagnosis/gene`, {
    method: 'POST',
    body: formData,
    signal: ctrl.signal,
  }).then(async (response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event = JSON.parse(line.slice(6));
            onEvent(event);
            if (event.step === 'complete' || event.step === 'error') {
              onComplete?.(event);
            }
          } catch { /* ignore */ }
        }
      }
    }
    onComplete?.({ step: 'stream_end' });
  }).catch((err) => {
    if (err.name !== 'AbortError') onError?.(err);
  });

  return () => ctrl.abort();
}

export async function healthCheck() {
  const res = await api.get('/health');
  return res.data;
}
