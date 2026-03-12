import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from '@/components/ui/sonner';
import { toast } from 'sonner';

// Pages
import { HomePage } from '@/pages/HomePage';
import { DashboardPage } from '@/pages/DashboardPage';
import { NewCasePage } from '@/pages/NewCasePage';
import { CasePage } from '@/pages/CasePage';
import { SectionPage } from '@/pages/SectionPage';
import { ExportPage } from '@/pages/ExportPage';

// Components
import { Navbar } from '@/components/Navbar';
import { Footer } from '@/components/Footer';

// API
import { getHealth } from '@/api/client';

function App() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    checkApiStatus();
  }, []);

  const checkApiStatus = async () => {
    try {
      await getHealth();
      setApiStatus('online');
    } catch (error) {
      setApiStatus('offline');
      toast.error('API server is offline. Please start the backend server.');
    }
  };

  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-slate-50">
        <Navbar apiStatus={apiStatus} />
        
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/new-case" element={<NewCasePage />} />
            <Route path="/case/:caseId" element={<CasePage />} />
            <Route path="/case/:caseId/section/:sectionName" element={<SectionPage />} />
            <Route path="/case/:caseId/export" element={<ExportPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        
        <Footer />
        <Toaster position="top-right" richColors />
      </div>
    </BrowserRouter>
  );
}

export default App;
