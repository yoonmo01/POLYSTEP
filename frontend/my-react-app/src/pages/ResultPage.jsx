import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ResultPage.css";

const mockResults = [
  {
    id: 1,
    title: "청년 주거 지원 바우처",
    category: "생활·주거",
    agency: "국토교통부 · 지자체",
    amount: "월 최대 20만 원",
    period: "최대 2년 지원",
    target: "만 19~34세 무주택 청년",
    url: "https://example.com/policy/1",
    tags: ["월세 지원", "단독 신청 가능"],
    score: "높음",
  },
  {
    id: 2,
    title: "청년 취업 성공 패키지",
    category: "일자리·취업",
    agency: "고용노동부",
    amount: "참여수당 및 취업 성공 수당",
    period: "최대 1년",
    target: "구직 중인 미취업 청년",
    url: "https://example.com/policy/2",
    tags: ["직무 교육", "컨설팅"],
    score: "매우 높음",
  },
  {
    id: 3,
    title: "대학생 등록금 지원 장학금",
    category: "교육·훈련",
    agency: "지자체 · 대학",
    amount: "등록금 일부 또는 전액",
    period: "1개 학기 기준",
    target: "소득 기준 충족 대학(원)생",
    url: "https://example.com/policy/3",
    tags: ["등록금", "소득연계"],
    score: "중간",
  },
];

function ResultPage() {
  const [selected, setSelected] = useState(mockResults[0]);
  const navigate = useNavigate();

  return (
    <div className="result-page">
      <div className="result-shell">
        <header className="result-header">
          <span className="result-step">STEP 3 · 추천 결과</span>
          <h1 className="result-title">지금 조건에 맞는 정책들을 찾았어요</h1>
          <p className="result-subtitle">
            연소득, 관심 분야, 취업 상태를 바탕으로
            <br className="only-mobile" />
            우선순위가 높은 정책부터 정리했어요.
          </p>
          {/* === 추가된 버튼 영역 === */}
          <div className="result-top-actions">
            <button
              type="button"
              className="result-back-btn"
              onClick={() => navigate("/question")}
            >
              ← 이전 단계로 돌아가기
            </button>

            <button
              type="button"
              className="result-next-btn"
              onClick={() => navigate("/final")}
            >
              최종 추천 보러가기 →
            </button>
          </div>
        </header>

        <div className="result-layout">
          {/* 왼쪽: 결과 리스트 */}
          <section className="result-list-panel">
            <div className="list-head">
              <p className="list-count">
                총 <strong>{mockResults.length}</strong>개의 추천 정책
              </p>
              <p className="list-hint">
                카드를 클릭하면 오른쪽에서 상세 내용을 볼 수 있어요.
              </p>
            </div>

            <div className="result-list">
              {mockResults.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={
                    "result-card" +
                    (selected && selected.id === item.id
                      ? " result-card-active"
                      : "")
                  }
                  onClick={() => setSelected(item)}
                >
                  <div className="result-card-main">
                    <h2 className="result-card-title">{item.title}</h2>
                    <p className="result-card-meta">
                      <span>{item.category}</span>
                      <span>·</span>
                      <span>{item.agency}</span>
                    </p>
                    <p className="result-card-desc">
                      지원 금액 <strong>{item.amount}</strong> / 지원 기간{" "}
                      <strong>{item.period}</strong>
                    </p>
                  </div>

                  <div className="result-card-bottom">
                    <div className="result-tags">
                      {item.tags.map((tag) => (
                        <span key={tag} className="result-tag">
                          {tag}
                        </span>
                      ))}
                    </div>
                    <span className="result-score-pill">
                      우선순위 {item.score}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </section>

          {/* 오른쪽: 상세 + iframe 자리 */}
          <section className="result-detail-panel">
            <div className="detail-card">
              {selected ? (
                <>
                  <div className="detail-head">
                    <span className="detail-category">
                      {selected.category}
                    </span>
                    <h2 className="detail-title">{selected.title}</h2>
                    <p className="detail-agency">{selected.agency}</p>
                  </div>

                  <div className="detail-info-grid">
                    <div className="detail-info-item">
                      <span className="label">지원 금액</span>
                      <span className="value">{selected.amount}</span>
                    </div>
                    <div className="detail-info-item">
                      <span className="label">지원 기간</span>
                      <span className="value">{selected.period}</span>
                    </div>
                    <div className="detail-info-item">
                      <span className="label">대상</span>
                      <span className="value">{selected.target}</span>
                    </div>
                    <div className="detail-info-item">
                      <span className="label">우선순위</span>
                      <span className="value">{selected.score}</span>
                    </div>
                  </div>

                  <div className="detail-tags-row">
                    {selected.tags.map((tag) => (
                      <span key={tag} className="detail-tag">
                        #{tag}
                      </span>
                    ))}
                  </div>

                  <div className="detail-iframe-block">
                    <div className="iframe-head">
                      <p className="iframe-title">정책 공식 홈페이지</p>
                      <p className="iframe-subtitle">
                        나중에 DB와 연동되면 이 영역에서 정책 신청 페이지를
                        바로 볼 수 있어요.
                      </p>
                    </div>

                    <div className="iframe-placeholder">
                      {/* 실제 연결 시 아래처럼 사용할 수 있음
                      <iframe
                        src={selected.url}
                        title={selected.title}
                        className="result-iframe"
                      />
                      */}
                      <p className="iframe-placeholder-text">
                        현재는 예시 데이터입니다.
                        <br />
                        추후 정책 API/DB를 연결한 뒤,
                        <br />
                        이 영역에 실제 정책 홈페이지가 열리도록 구현할 수 있어요.
                      </p>
                    </div>
                  </div>

                  <div className="detail-footer">
                    <button
                      type="button"
                      className="detail-link-btn"
                      onClick={() => {
                        // 임시: 새 탭으로 예시 URL 열기
                        if (selected.url) {
                          window.open(selected.url, "_blank", "noopener");
                        }
                      }}
                    >
                      정책 홈페이지 새 탭에서 열기
                    </button>
                  </div>
                </>
              ) : (
                <div className="detail-empty">
                  <p>왼쪽에서 보고 싶은 정책 카드를 선택해 주세요.</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

export default ResultPage;
