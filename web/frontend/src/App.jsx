import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import HomePage from './pages/HomePage';
import HPOExtractionPage from './pages/HPOExtractionPage';
import DiagnosisPage from './pages/DiagnosisPage';
import GeneDiagnosisPage from './pages/GeneDiagnosisPage';
import SettingsPage from './pages/SettingsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<HomePage />} />
          <Route path="hpo" element={<HPOExtractionPage />} />
          <Route path="diagnosis" element={<DiagnosisPage />} />
          <Route path="gene-diagnosis" element={<GeneDiagnosisPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
