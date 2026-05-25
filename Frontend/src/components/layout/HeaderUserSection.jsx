import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

export default function HeaderUserSection() {
  const navigate = useNavigate();
  const { isAuthenticated, user } = useAuth();

  if (!isAuthenticated || !user) {
    return (
      <Link className="user-mini-card user-mini-card-button" to="/auth">
        登录 / 注册
      </Link>
    );
  }

  return (
    <div className="user-header-actions">
      {user.role === "admin" ? (
        <Link className="admin-mini-link" to="/admin">
          后台管理
        </Link>
      ) : null}
      <button className="user-mini-card" onClick={() => navigate("/me")} type="button">
        <span className="user-mini-line" />
        <strong>{user.phone_masked}</strong>
        <span>{user.nickname || user.username}</span>
      </button>
    </div>
  );
}
