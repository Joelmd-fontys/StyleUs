import { Navigate, Route, Routes } from 'react-router-dom';
import AuthGate from './auth/AuthGate';
import AppShell from './components/AppShell';
import Dashboard from './pages/Dashboard';
import ItemDetail from './pages/ItemDetail';
import Outfits from './pages/Outfits';
import Settings from './pages/Settings';
import Wardrobe from './pages/Wardrobe';
import UploadReviewPage from './pages/UploadReviewPage';

const App = () => {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <AuthGate>
            <AppShell />
          </AuthGate>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="wardrobe" element={<Wardrobe />} />
        <Route path="items/:id" element={<ItemDetail />} />
        <Route path="outfits" element={<Outfits />} />
        <Route path="settings" element={<Settings />} />
        <Route path="upload/review/:id" element={<UploadReviewPage />} />
        <Route path="*" element={<Navigate to="/wardrobe" replace />} />
      </Route>
    </Routes>
  );
};

export default App;
