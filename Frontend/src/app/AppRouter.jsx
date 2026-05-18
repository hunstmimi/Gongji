import { Navigate, Route, Routes } from "react-router-dom";
import CoverPage from "../pages/CoverPage";
import CatalogPage from "../pages/CatalogPage";
import ResultPage from "../pages/ResultPage";
import AuthPage from "../pages/AuthPage";
import ProfilePage from "../pages/ProfilePage";
import ProtectedRoute from "../components/layout/ProtectedRoute";

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<CoverPage />} />
      <Route path="/auth" element={<AuthPage />} />
      <Route
        path="/catalog"
        element={
          <ProtectedRoute>
            <CatalogPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/result"
        element={
          <ProtectedRoute>
            <ResultPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/me"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
