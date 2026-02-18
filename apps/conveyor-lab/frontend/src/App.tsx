/**
 * Main App component with routing
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { HMIStatusPage } from './pages/HMIStatusPage';
import { NewRunPage } from './pages/NewRunPage';
import { RunsListPage } from './pages/RunsListPage';
import { RunDetailPage } from './pages/RunDetailPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 5000,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HMIStatusPage />} />
          <Route path="/new-run" element={<NewRunPage />} />
          <Route path="/runs" element={<RunsListPage />} />
          <Route path="/runs/:id" element={<RunDetailPage />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
