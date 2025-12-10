import { useNavigate } from "react-router-dom";

function HomePage() {
  const navigate = useNavigate();

  return (
    <section className="page home-page">
      <div className="hero">
        <h1>POLYSTEP</h1>
        <p>청년을 위한 맞춤 정책 길잡이</p>

        <div className="home-buttons">
          <button onClick={() => navigate("/login")}>로그인</button>
          <button onClick={() => navigate("/signup")}>회원가입</button>
          <button onClick={() => navigate("/main")}>홈페이지로 이동</button>
        </div>
      </div>
    </section>
  );
}

export default HomePage;
