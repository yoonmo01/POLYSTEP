import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { setUser } from "../auth";
import "./SignupPage.css";

function SignupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    passwordConfirm: "",
    age: "",
    region: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (form.password !== form.passwordConfirm) {
      alert("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
      return;
    }

    setUser({ name: form.name, email: form.email, age: form.age, region: form.region });

    navigate("/");
  };


  return (
    <div className="auth-page">
      <div className="auth-shell">
        <section className="auth-card">
          <div className="auth-header">
            <span className="auth-step">SIGN UP</span>
            <h1 className="auth-title">회원가입을 진행할게요</h1>
            <p className="auth-subtitle">
              계정 정보 + 기본 정보(나이/거주지역)만 입력하면 완료됩니다.
            </p>
          </div>

          <form className="auth-form" onSubmit={handleSubmit}>
            <div className="auth-grid">
              <div className="auth-field">
                <label htmlFor="name">이름</label>
                <input
                  id="name"
                  name="name"
                  type="text"
                  value={form.name}
                  onChange={handleChange}
                  placeholder="홍길동"
                  required
                />
              </div>

              <div className="auth-field">
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

              <div className="auth-field">
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

              <div className="auth-field">
                <label htmlFor="passwordConfirm">비밀번호 확인</label>
                <input
                  id="passwordConfirm"
                  name="passwordConfirm"
                  type="password"
                  value={form.passwordConfirm}
                  onChange={handleChange}
                  placeholder="다시 한 번 입력"
                  required
                />
              </div>

              {/* ✅ 추가: 나이 + 거주지역만 */}
              <div className="auth-field">
                <label htmlFor="age">나이</label>
                <input
                  id="age"
                  name="age"
                  type="number"
                  min="0"
                  value={form.age}
                  onChange={handleChange}
                  placeholder="예: 24"
                  required
                />
              </div>

              <div className="auth-field">
                <label htmlFor="region">거주 지역</label>
                <input
                  id="region"
                  name="region"
                  type="text"
                  value={form.region}
                  onChange={handleChange}
                  placeholder="예: 강원도 춘천시"
                  required
                />
              </div>
            </div>

            <div className="auth-footer">
              <p className="auth-hint">
                이미 계정이 있나요?{" "}
                <Link to="/login" className="auth-link">
                  로그인
                </Link>
              </p>

              <button type="submit" className="auth-submit-btn">
                회원가입 완료
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default SignupPage;
