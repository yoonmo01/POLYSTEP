import { useNavigate } from "react-router-dom";

function MainPage() {
  const navigate = useNavigate();

  return (
    <div className="page main-page">
      {/* 상단 영역 = 설계서 5페이지 */}
      <section className="main-section main-top">
        <div className="main-top-content">
          <h2>나에게 맞는 정책을 한 번에</h2>
          <p>POLYSTEP에서 지역, 연령, 상황에 맞는 정책을 찾아보세요.</p>

          {/* 가운데 버튼 → 7페이지 (QuestionPage) */}
          <button
            className="primary-btn"
            onClick={() => navigate("/question")}
          >
            나만의 정책 찾기
          </button>
        </div>
      </section>

      {/* 아래로 이어지는 영역 = 설계서 6페이지 */}
      <section className="main-section main-bottom">
        <h3>추천 서비스</h3>
        <div className="card-grid">
          <div className="card">
            <h4>분야별 정책 보기</h4>
            <p>취업, 주거, 생활비 등 카테고리별 정책을 한 번에.</p>
          </div>
          <div className="card">
            <h4>지역별 정책 보기</h4>
            <p>현재 거주지/관심 지역 기준 정책 모아보기.</p>
          </div>
          <div className="card">
            <h4>최근 본 정책</h4>
            <p>최근 확인한 정책 목록을 다시 확인할 수 있어요.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

export default MainPage;
