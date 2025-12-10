function LoginPage() {
  const handleSubmit = (e) => {
    e.preventDefault();
    // 실제 로그인 로직은 나중에
  };

  return (
    <section className="page login-page">
      <h2>로그인</h2>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label>
          이메일
          <input type="email" placeholder="이메일을 입력하세요" />
        </label>
        <label>
          비밀번호
          <input type="password" placeholder="비밀번호를 입력하세요" />
        </label>
        <button type="submit">로그인</button>
      </form>
    </section>
  );
}

export default LoginPage;
