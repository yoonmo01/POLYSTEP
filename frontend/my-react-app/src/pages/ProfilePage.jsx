import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ProfilePage.css";

function ProfilePage() {
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

    if (form.password && form.password !== form.passwordConfirm) {
      alert("비밀번호와 비밀번호 확인이 일치하지 않습니다.");
      return;
    }

    console.log("프로필 정보:", form);
    // TODO: 나중에 전역 상태 / 백엔드 연동

    navigate("/question");
  };

  return (
    <div className="profile-page">
      <div className="profile-shell">
        <section className="profile-card">
          <div className="profile-header">
            <span className="profile-step">STEP 1 · 기본 프로필</span>
            <h1 className="profile-title">나를 위한 정책 추천을 준비할게요</h1>
            <p className="profile-subtitle">
              폴리스탭이 추천을 만들 수 있도록
              <br className="only-mobile" />
              기본 정보를 간단히 입력해 주세요.
            </p>
          </div>

          <form className="profile-form" onSubmit={handleSubmit}>
            <div className="profile-grid">
              <div className="profile-field">
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

              <div className="profile-field">
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

              <div className="profile-field">
                <label htmlFor="password">비밀번호</label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  value={form.password}
                  onChange={handleChange}
                  placeholder="로그인용 비밀번호"
                />
              </div>

              <div className="profile-field">
                <label htmlFor="passwordConfirm">비밀번호 확인</label>
                <input
                  id="passwordConfirm"
                  name="passwordConfirm"
                  type="password"
                  value={form.passwordConfirm}
                  onChange={handleChange}
                  placeholder="다시 한 번 입력"
                />
              </div>

              <div className="profile-field">
                <label htmlFor="age">나이</label>
                <input
                  id="age"
                  name="age"
                  type="number"
                  min="0"
                  value={form.age}
                  onChange={handleChange}
                  placeholder="예: 24"
                />
              </div>

              <div className="profile-field">
                <label htmlFor="region">거주 지역</label>
                <input
                  id="region"
                  name="region"
                  type="text"
                  value={form.region}
                  onChange={handleChange}
                  placeholder="예: 강원도 춘천시"
                />
              </div>
            </div>

            <div className="profile-footer">
              <p className="profile-hint">
                입력한 정보는 추천 정책 계산에만 사용되며,
                <br className="only-mobile" />
                언제든지 마이페이지에서 수정할 수 있어요.
              </p>
              <button type="submit" className="profile-submit-btn">
                다음 단계로 이동하기
              </button>
            </div>
          </form>
        </section>
      </div>
    </div>
  );
}

export default ProfilePage;
