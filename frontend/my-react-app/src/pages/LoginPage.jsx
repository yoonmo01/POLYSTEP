import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import "./LoginPage.css";

function LoginPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    // TODO: 나중에 백엔드 로그인 연동
    console.log("로그인 정보:", form);

    // ✅ 로그인 완료 → 홈
    navigate("/");
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

              <button type="submit" className="auth-submit-btn">
                로그인
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default LoginPage;

