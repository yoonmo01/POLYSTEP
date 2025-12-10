import { useNavigate } from "react-router-dom";

function FinalPage() {
  const navigate = useNavigate();

  return (
    <section className="page final-page">
      <h2>나에게 맞는 POLYSTEP 결과</h2>
      <p>
        지금까지 선택한 정보와 추천 결과를 기반으로
        <br />
        나만의 정책 요약 페이지를 만들었어요.
      </p>

      <div className="summary-box">
        <h3>요약</h3>
        <ul>
          <li>주요 추천 정책 3개</li>
          <li>관심 분야: 취업 / 주거 / 생활비</li>
          <li>추가로 확인하면 좋은 정책들 안내</li>
        </ul>
      </div>

      <button className="primary-btn" onClick={() => navigate("/mypage")}>
        마이 페이지로 이동
      </button>
    </section>
  );
}

export default FinalPage;
