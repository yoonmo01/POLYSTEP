function SignupPage() {
  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: 회원가입 처리 로직 (백엔드 연결 후 구현)
  };

  return (
    <section className="page signup-page">
      <h2>회원가입</h2>
      <p className="subtitle">
        POLYSTEP를 이용하기 위해 기본 정보를 입력해 주세요.
      </p>

      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          이름
          <input type="text" placeholder="이름을 입력하세요" required />
        </label>

        <label>
          이메일
          <input type="email" placeholder="이메일을 입력하세요" required />
        </label>

        <label>
          비밀번호
          <input type="password" placeholder="비밀번호를 입력하세요" required />
        </label>

        <label>
          비밀번호 확인
          <input
            type="password"
            placeholder="비밀번호를 다시 입력하세요"
            required
          />
        </label>

        <label>
          나이
          <input type="number" placeholder="예: 24" />
        </label>

        <label>
          거주 지역
          <input type="text" placeholder="예: 강원도 춘천시" />
        </label>

        <label className="checkbox-row">
          <input type="checkbox" required />
          <span>서비스 이용약관 및 개인정보 수집·이용에 동의합니다.</span>
        </label>

        <button type="submit" className="primary-btn">
          회원가입 완료
        </button>
      </form>
    </section>
  );
}

export default SignupPage;
