import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function ProtectedRoute({ children }) {
  const location = useLocation();
  const { isAuthenticated, ready } = useAuth();

  if (!ready) {
    return <div className="empty-state">正在恢复登录状态...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/auth" replace state={{ from: location.pathname + location.search }} />;
  }

  return children;
}
