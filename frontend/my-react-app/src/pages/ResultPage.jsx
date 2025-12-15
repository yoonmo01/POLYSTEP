import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ResultPage.css";

// ✅ 여기 mockResults는 너 기존 ResultPage가 갖고 있던 데이터로 교체해도 됨
const mockResults = [
  {
    id: 1,
    title: "청년 주거 지원 바우처",
    category: "생활·주거",
    agency: "국토교통부 · 지자체",
    amount: "월 최대 20만 원",
    period: "최대 2년 지원",
    target: "만 19~34세 무주택 청년",
    url: "https://example.com",
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
    url: "https://example.com",
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
    url: "https://example.com",
    tags: ["등록금", "소득연계"],
    score: "중간",
  },
];

function ResultPage() {
  const navigate = useNavigate();

  const [selected, setSelected] = useState(mockResults[0]);
  const [verifyLogs, setVerifyLogs] = useState([]);
  const [isVerifying, setIsVerifying] = useState(false);

  const iframeSrc = useMemo(() => selected?.url || "", [selected]);

  const pushLog = (msg) => {
    const ts = new Date().toLocaleTimeString("ko-KR", { hour12: false });
    setVerifyLogs((prev) => [...prev, `[${ts}] ${msg}`]);
  };

  const handleVerify = () => {
    if (!selected) return;
    if (isVerifying) return;

    setIsVerifying(true);
    setVerifyLogs([]);

    pushLog(`검증 시작: "${selected.title}"`);
    pushLog("입력 조건 로드...");
    setTimeout(() => pushLog("자격 조건 매칭 계산 중..."), 400);
    setTimeout(() => pushLog("우선순위 점수 재평가 중..."), 900);
    setTimeout(() => pushLog("공식 신청 페이지 URL 확인 중..."), 1300);
    setTimeout(() => {
      pushLog("검증 완료 ✅ (현재는 UI 데모 로그)");
      setIsVerifying(false);
    }, 1700);
  };

  return (
    <div className="result-page">
      <div className="result-shell">
        <header className="result-header">
          <span className="result-step">STEP 2 · 추천 결과</span>
          <h1 className="result-title">지금 조건에 맞는 정책들을 찾았어요</h1>
          <p className="result-subtitle">
            선택한 조건을 바탕으로 우선순위가 높은 정책부터 정리했어요.
          </p>

          <div className="result-top-actions">
            <button
              type="button"
              className="result-back-btn"
              onClick={() => navigate("/question")}
            >
              ← 이전 단계로
            </button>
            <button
              type="button"
              className="result-next-btn"
              onClick={() => navigate("/final")}
            >
              최종 추천 →
            </button>
          </div>
        </header>

        <div className="result-layout">
          {/* ✅ 왼쪽 리스트 패널 (기존 디자인 그대로 사용) */}
          <section className="result-list-panel">
            <div className="list-head">
              <p className="list-count">
                총 <strong>{mockResults.length}</strong>개의 추천 정책
              </p>
              <p className="list-hint">
                카드를 클릭하면 오른쪽에서 해당 정책 페이지를 바로 볼 수 있어요.
              </p>
            </div>

            <div className="result-list">
              {mockResults.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={
                    "result-card" +
                    (selected?.id === item.id ? " result-card-active" : "")
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

          {/* ✅ 오른쪽 상세 패널: “텍스트 제거” + “전체를 iframe” */}
          <section className="result-detail-panel">
            <div className="detail-card" style={{ height: "100%" }}>
              <div
                className="detail-iframe-block"
                style={{
                  width: "100%",
                  height: "100%",
                  minHeight: 520,
                }}
              >
                {selected?.url ? (
                  <iframe
                    src={iframeSrc}
                    title={selected.title}
                    className="result-iframe"
                    loading="lazy"
                    style={{
                      height: "100%", // ✅ 기존 CSS의 260px을 덮어씀
                      borderRadius: 14,
                    }}
                  />
                ) : (
                  <div className="detail-empty">
                    정책 URL이 아직 없어요. (추후 DB 연결 예정)
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* ✅ 아래 섹션 1개 추가: “검증 로그 스페이스” */}
        <section
          className="result-list-panel"
          style={{ marginTop: "1.4rem", padding: "1.4rem" }}
        >
          <div
            className="list-head"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-end",
              gap: "1rem",
            }}
          >
            <div>
              <p className="list-count" style={{ marginBottom: 4 }}>
                검증 로그
              </p>
              <p className="list-hint" style={{ marginTop: 0 }}>
                “검증하기”를 누르면 검증 과정을 로그로 출력합니다.
              </p>
            </div>

            <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
              <button
                type="button"
                className="result-next-btn"
                onClick={handleVerify}
                disabled={isVerifying}
              >
                {isVerifying ? "검증 중..." : "검증하기"}
              </button>
              <button
                type="button"
                className="result-back-btn"
                onClick={() => setVerifyLogs([])}
                disabled={verifyLogs.length === 0 || isVerifying}
              >
                로그 지우기
              </button>
            </div>
          </div>

          <div
            style={{
              marginTop: "0.9rem",
              borderRadius: 14,
              border: "1px solid rgba(148, 163, 184, 0.35)",
              background: "rgba(15, 23, 42, 0.9)",
              padding: "0.9rem 1rem",
              minHeight: 160,
              maxHeight: 260,
              overflow: "auto",
            }}
          >
            {verifyLogs.length === 0 ? (
              <p style={{ margin: 0, color: "#9ca3af", fontSize: "0.85rem" }}>
                아직 로그가 없어요. “검증하기”를 눌러보세요.
              </p>
            ) : (
              <ul
                style={{
                  margin: 0,
                  paddingLeft: "1.1rem",
                  color: "#e5e7eb",
                  fontSize: "0.85rem",
                  lineHeight: 1.55,
                }}
              >
                {verifyLogs.map((line, idx) => (
                  <li key={`${line}-${idx}`}>{line}</li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

export default ResultPage;
