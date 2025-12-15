import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./QuestionPage.css";

function QuestionPage() {
  const navigate = useNavigate();

  // 상태 관리
  const [income, setIncome] = useState("");
  const [policyField, setPolicyField] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [specialField, setSpecialField] = useState(null);

  // 버튼 옵션들 (나중에 DB 기준에 맞게 텍스트만 수정하면 됨)
  const policyOptions = [
    "생활·주거",
    "교육·훈련",
    "일자리·창업",
    "금융·대출",
    "문화·교통",
  ];

  const jobOptions = [
    "재학/휴학 중",
    "졸업 후 취업 준비",
    "재직 중",
    "프리랜서/자영업",
    "기타/무응답",
  ];

  const specialOptions = [
    "청년 일반",
    "저소득/취약계층",
    "대학생/청년 인턴",
    "창업·소상공인",
    "지역 정착/귀향",
  ];

  const handleSubmit = (e) => {
    e.preventDefault();

    // 간단한 유효성 검사
    if (!income || !policyField || !jobStatus) {
      alert("연소득, 정책 분야, 취업 상태는 최소 한 번씩 선택해 주세요.");
      return;
    }

    // TODO: 선택값을 전역 상태/쿼리스트링 등으로 넘겨서 ResultPage에서 활용
    console.log({
      income,
      policyField,
      jobStatus,
      specialField,
    });

    navigate("/result");
  };

  return (
    <div className="question-page">
      <div className="question-shell">
        <header className="question-header">
          <span className="question-step">STEP 1 · 조건 선택</span>
          <h1 className="question-title">지금 상황에 맞는 조건을 알려주세요</h1>
          <p className="question-subtitle">
            폴리스탭이 수많은 정책 중에서
            <br className="only-mobile" />
            지금 나에게 맞는 것만 골라낼 수 있도록 도와줄게요.
          </p>
        </header>

        <form className="question-form" onSubmit={handleSubmit}>
          {/* 섹션 1: 연소득 */}
          <section className="question-section">
            <div className="section-head">
              <h2>1. 현재 연소득</h2>
              <p>대략적인 금액만 입력해도 괜찮아요. (단위: 만 원)</p>
            </div>
            <div className="section-body">
              <div className="income-field">
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={income}
                  onChange={(e) => setIncome(e.target.value)}
                  placeholder="예: 1200 (연 1,200만 원)"
                />
                <span className="income-unit">만 원 / 년</span>
              </div>
              <p className="section-hint">
                소득 조건이 있는 주거·생활·금융 정책 필터링에 활용돼요.
              </p>
            </div>
          </section>

          {/* 섹션 2: 관심 정책 분야 */}
          <section className="question-section">
            <div className="section-head">
              <h2>2. 관심 있는 정책 분야</h2>
              <p>가장 먼저 안내받고 싶은 분야를 선택해 주세요.</p>
            </div>
            <div className="section-body">
              <div className="chip-row">
                {policyOptions.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    className={
                      "chip-btn" +
                      (policyField === opt ? " chip-btn-active" : "")
                    }
                    onClick={() => setPolicyField(opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* 섹션 3: 현재 취업 상태 */}
          <section className="question-section">
            <div className="section-head">
              <h2>3. 현재 취업 상태</h2>
              <p>가장 가까운 상태 하나를 선택해 주세요.</p>
            </div>
            <div className="section-body">
              <div className="chip-row">
                {jobOptions.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    className={
                      "chip-btn" + (jobStatus === opt ? " chip-btn-active" : "")
                    }
                    onClick={() => setJobStatus(opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* 섹션 4: 특화 대상 여부 */}
          <section className="question-section">
            <div className="section-head">
              <h2>4. 해당되는 특화 대상이 있나요?</h2>
              <p>있다면 선택해 주세요. 없으면 건너뛰어도 괜찮아요.</p>
            </div>
            <div className="section-body">
              <div className="chip-row">
                {specialOptions.map((opt) => (
                  <button
                    type="button"
                    key={opt}
                    className={
                      "chip-btn" +
                      (specialField === opt ? " chip-btn-active" : "")
                    }
                    onClick={() =>
                      setSpecialField((prev) => (prev === opt ? null : opt))
                    }
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>
          </section>

          {/* 요약 + 제출 */}
          <footer className="question-footer">
            <div className="summary">
              <p className="summary-title">선택한 조건</p>
              <div className="summary-chips">
                {income && (
                  <span className="summary-chip">연 {income}만 원</span>
                )}
                {policyField && (
                  <span className="summary-chip">{policyField}</span>
                )}
                {jobStatus && (
                  <span className="summary-chip">{jobStatus}</span>
                )}
                {specialField && (
                  <span className="summary-chip">{specialField}</span>
                )}
                {!income && !policyField && !jobStatus && !specialField && (
                  <span className="summary-placeholder">
                    아직 선택된 조건이 없어요.
                  </span>
                )}
              </div>
            </div>

            <button type="submit" className="question-submit-btn">
              이 조건으로 정책 추천 받기
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

export default QuestionPage;
