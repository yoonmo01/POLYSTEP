import "./FinalPage.css";
import { useNavigate } from "react-router-dom";

function FinalPage() {
  const navigate = useNavigate();

  // TODO: 실제로는 ResultPage에서 선택한 정책 정보를 넘겨받도록 수정
  const finalPolicy = {
    title: "청년 주거 지원 바우처 (예시)",
    agency: "국토교통부 · 지자체",
    category: "생활·주거",
    amount: "월 최대 20만 원",
    period: "최대 2년 지원",
    target: "만 19~34세 무주택 청년",
    why: [
      "입력한 연소득과 나이를 기준으로 우선순위가 높게 평가됐어요.",
      "관심 분야로 선택한 ‘생활·주거’ 분야 정책과 잘 맞아요.",
      "현재 취업 상태에서 신청 가능성이 높은 조건이에요.",
    ],
  };

  return (
    <div className="final-page">
      <div className="final-shell">
        <header className="final-header">
          <span className="final-step">STEP 4 · 최종 추천</span>
          <h1 className="final-title">지금, 나에게 가장 잘 맞는 정책이에요</h1>
          <p className="final-subtitle">
            입력한 프로필과 조건을 바탕으로
            <br className="only-mobile" />
            폴리스탭이 하나의 핵심 정책을 골라봤어요.
          </p>
        </header>

        <main className="final-main">
          {/* 상단 메인 카드 */}
          <section className="final-hero-card">
            <div className="final-icon-circle">✨</div>
            <p className="final-hero-label">나의 최종 추천 정책</p>
            <h2 className="final-hero-title">{finalPolicy.title}</h2>
            <p className="final-hero-meta">
              {finalPolicy.category} · {finalPolicy.agency}
            </p>

            <div className="final-hero-info-row">
              <div className="info-pill">
                <span className="info-label">지원 금액</span>
                <span className="info-value">{finalPolicy.amount}</span>
              </div>
              <div className="info-pill">
                <span className="info-label">지원 기간</span>
                <span className="info-value">{finalPolicy.period}</span>
              </div>
              <div className="info-pill long">
                <span className="info-label">지원 대상</span>
                <span className="info-value">{finalPolicy.target}</span>
              </div>
            </div>
          </section>

          {/* 왜 이 정책인지 설명 */}
          <section className="final-why-card">
            <h3 className="final-why-title">이 정책을 추천한 이유</h3>
            <ul className="final-why-list">
              {finalPolicy.why.map((reason, idx) => (
                <li key={idx}>{reason}</li>
              ))}
            </ul>
            <p className="final-why-hint">
              실제 서비스에서는 정책 데이터와 추천 알고리즘을 연결해,
              나에게 딱 맞는 정책을 자동으로 계산할 수 있어요.
            </p>
          </section>

          {/* 다음 액션 */}
          <section className="final-actions">
            <button
              type="button"
              className="final-primary-btn"
              onClick={() => navigate("/mypage")}
            >
              마이페이지에서 추천 결과 모아보기
            </button>
            <button
              type="button"
              className="final-secondary-btn"
              onClick={() => navigate("/")}
            >
              처음으로 돌아가 다시 찾아보기
            </button>
          </section>
        </main>
      </div>
    </div>
  );
}

export default FinalPage;
