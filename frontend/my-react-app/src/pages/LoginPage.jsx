//frontend/my-react-app/src/pages/LoginPage.jsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { setUser, setToken } from "../auth";
import "./LoginPage.css";

function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [isSubmitting, setIsSubmitting] = useState(false);

  const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  const loginRequest = async ({ email, password }) => {
    const res = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || "로그인에 실패했습니다.");
    return data; // { access_token, token_type }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (isSubmitting) return;
    setIsSubmitting(true);

    try {
      const tokenRes = await loginRequest(form);
      setToken(tokenRes.access_token);

      // ✅ 백엔드에 /auth/me가 아직 없어서, UI 표시용 user는 최소 정보로 저장
      setUser({ name: "사용자", email: form.email });

      navigate("/");
    } catch (err) {
      alert(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-shell">
        <section className="auth-card">
          <div className="auth-header">
            <span className="auth-step">LOGIN</span>
            <h1 className="auth-title">다시 만나서 반가워요</h1>
            <p className="auth-subtitle">
              이메일과 비밀번호를 입력하면
              <br className="only-mobile" />
              홈으로 이동합니다.
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-grid">
              <div className="auth-field auth-span-2">
                <label htmlFor="email">이메일</label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  value={form.email}
                  onChange={handleChange}
                  placeholder="example@email.com"
                  required
                />
              </div>

              <div className="auth-field auth-span-2">
                <label htmlFor="password">비밀번호</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="로그인용 비밀번호"
                  required
                />
              </div>
            </div>

            <div className="auth-footer">
              <p className="auth-hint">
                계정이 없나요?{" "}
                <Link to="/signup" className="auth-link">
                  회원가입
                </Link>
              </p>

              <button type="submit" className="auth-submit-btn" disabled={isSubmitting}>
                {isSubmitting ? "로그인 중..." : "로그인"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default LoginPage;

