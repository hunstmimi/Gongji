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
    <button className="user-mini-card" onClick={() => navigate("/me")}>
      <span className="user-mini-line" />
      <strong>{user.phone_masked}</strong>
      <span>{user.username}</span>
    </button>
  );
}
