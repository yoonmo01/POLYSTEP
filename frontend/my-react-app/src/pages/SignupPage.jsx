//frontend/my-react-app/src/pages/SignupPage.jsx
import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { setUser, setToken } from "../auth";
import "./SignupPage.css";

function SignupPage() {
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const API_BASE_URL =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  const registerRequest = async ({
    email,
    password,
    full_name,
    age,
    region,
    is_student,
    academic_status,
    major,
    grade,
    gpa,
  }) => {
    const res = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        full_name,
        age,
        region,
        is_student,
        academic_status,
        major,
        grade,
        gpa,
      }),
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(data?.detail || "회원가입에 실패했습니다.");
    return data; // UserRead
  };

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
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    passwordConfirm: "",
    age: "",
    region: "",
    is_student: false,
    academic_status: "",
    major: "",
    grade: "",
    gpa: "",
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (e.target.type === "checkbox") {
      setForm((prev) => ({ ...prev, [name]: e.target.checked }));
    } else {
      setForm((prev) => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (form.password !== form.passwordConfirm) {
      alert("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
      return;
    }
    // ✅ 숫자 변환(빈 문자열 방지)
    const ageNum =
      form.age === "" || form.age == null ? null : Number(form.age);
    const gradeNum =
      form.grade === "" || form.grade == null ? null : Number(form.grade);
    const gpaNum =
      form.gpa === "" || form.gpa == null ? null : Number(form.gpa);
    if (ageNum == null || Number.isNaN(ageNum) || ageNum < 0) {
      alert("나이를 올바르게 입력해 주세요.");
      return;
    }
    if (!form.region?.trim()) {
      alert("거주 지역을 입력해 주세요.");
      return;
    }
    if (isSubmitting) return;
    setIsSubmitting(true);

    try {
      // 1) 회원가입
      await registerRequest({
        email: form.email,
        password: form.password,
        full_name: form.name,
        age: ageNum,
        region: form.region.trim(),
        is_student: true,
        academic_status: form.academic_status,
        major: form.major,
        grade: gradeNum,
        gpa: gpaNum,
      });

      // 2) 자동 로그인 → 토큰 저장
      const tokenRes = await loginRequest({
        email: form.email,
        password: form.password,
      });
      setToken(tokenRes.access_token);

      // 3) UI/필터용 프로필 로컬 저장 (age/region은 프론트에서만 사용 가능)
      setUser({
        name: form.name,
        email: form.email,
        age: ageNum,
        region: form.region.trim(),
        is_student: form.is_student,
        academic_status: form.academic_status,
        major: form.major,
        grade: form.grade,
        gpa: form.gpa,
      });

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
              {/* 학적 상태 */}
              <div className="auth-field">
                <label htmlFor="academic_status">학적 상태</label>
                <select
                  id="academic_status"
                  name="academic_status"
                  value={form.academic_status}
                  onChange={handleChange}
                  required
                >
                  <option value="">선택</option>
                  <option value="재학">재학</option>
                  <option value="휴학">휴학</option>
                  <option value="졸업예정">졸업예정</option>
                  <option value="졸업">졸업</option>
                </select>
              </div>

              <div className="auth-field">
                <label htmlFor="major">전공</label>
                <input
                  id="major"
                  name="major"
                  type="text"
                  value={form.major}
                  onChange={handleChange}
                  placeholder="예: 컴퓨터공학"
                  required
                />
              </div>

              <div className="auth-field">
                <label htmlFor="grade">학년</label>
                <input
                  id="grade"
                  name="grade"
                  type="number"
                  min="1"
                  max="6"
                  value={form.grade}
                  onChange={handleChange}
                  required
                />
              </div>

              <div className="auth-field">
                <label htmlFor="gpa">평균 평점</label>
                <input
                  id="gpa"
                  name="gpa"
                  type="number"
                  step="0.01"
                  min="0"
                  max="4.5"
                  value={form.gpa}
                  onChange={handleChange}
                  placeholder="예: 3.5"
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

              <button type="submit" className="auth-submit-btn" disabled={isSubmitting}>
                {isSubmitting ? "가입 중..." : "회원가입 완료"}
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default SignupPage;
