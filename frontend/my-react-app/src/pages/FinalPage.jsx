// frontend/my-react-app/src/pages/FinalPage.jsx
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import "./FinalPage.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function FinalPage() {
  const navigate = useNavigate();
  const { policyId } = useParams();

  const [policy, setPolicy] = useState(null);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        const [policyRes, verifyRes] = await Promise.all([
          fetch(`${API_BASE}/policies/${policyId}`, { credentials: "include" }),
          fetch(`${API_BASE}/policies/${policyId}/verification`, {
            credentials: "include",
          }),
        ]);

        if (!policyRes.ok) throw new Error("정책 정보를 불러올 수 없습니다.");
        if (!verifyRes.ok) throw new Error("검증 결과를 불러올 수 없습니다.");

        const policyData = await policyRes.json();
        const verifyData = await verifyRes.json();

        setPolicy(policyData);
        setVerification(verifyData);
      } catch (e) {
        setError(e.message || "데이터 로딩 실패");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [policyId]);

  if (loading) {
    return <div className="final-page">로딩 중...</div>;
  }

  if (error) {
    return (
      <div className="final-page">
        <p style={{ color: "red" }}>{error}</p>
        <button onClick={() => navigate(-1)}>뒤로가기</button>
      </div>
    );
  }

  const ec = verification.extracted_criteria;

  return (
    <div className="final-page">
      <div className="final-shell">
        <header className="final-header">
          <span className="final-step">STEP 3 · 최종 추천</span>
          <h1 className="final-title">{policy.title}</h1>
          <p className="final-subtitle">
            자동 검증 결과를 바탕으로 신청 절차를 정리했어요
          </p>
        </header>

        {/* ✅ 신청 요약 */}
        <section className="final-hero-card">
          <div className="final-hero-info-row">
            <div className="info-pill">
              <span className="info-label">신청 방식</span>
              <span className="info-value">{ec.apply_channel}</span>
            </div>
            <div className="info-pill">
              <span className="info-label">신청 기간</span>
              <span className="info-value">{ec.apply_period}</span>
            </div>
            <div className="info-pill long">
              <span className="info-label">문의</span>
              <span className="info-value">
                {ec.contact?.org} · {ec.contact?.tel}
              </span>
            </div>
          </div>
        </section>

        {/* ✅ Step-by-Step 신청 절차 */}
        <section className="final-steps">
          <h3>신청 절차</h3>
          <ol className="final-step-list">
            {ec.apply_steps.map((step) => (
              <li key={step.step} className="final-step-item">
                <strong>
                  STEP {step.step}. {step.title}
                </strong>
                <p>{step.detail}</p>
                {step.url && (
                  <a href={step.url} target="_blank" rel="noreferrer">
                    바로가기 →
                  </a>
                )}
              </li>
            ))}
          </ol>
        </section>

        {/* ✅ 준비 서류 */}
        <section className="final-docs">
          <h3>필요 서류</h3>
          <ul>
            {ec.required_documents.map((doc, idx) => (
              <li key={idx}>📄 {doc}</li>
            ))}
          </ul>
        </section>

        {/* ✅ 자격 요건 */}
        <section className="final-criteria">
          <h3>자격 요건 요약</h3>
          <ul>
            {Object.entries(ec.criteria).map(([key, val]) => (
              <li key={key}>
                <strong>{key}</strong>: {val}
              </li>
            ))}
          </ul>
        </section>

        {/* ✅ 근거 & 투명성 */}
        <section className="final-evidence">
          <h3>검증 근거</h3>
          <pre>{verification.evidence_text}</pre>
        </section>

        {/* ✅ 네비게이션 경로 */}
        <section className="final-path">
          <h3>탐색 경로</h3>
          <ol>
            {verification.navigation_path.map((p, idx) => (
              <li key={idx}>
                [{p.action}] {p.label}
              </li>
            ))}
          </ol>
        </section>

        {/* 액션 */}
        <section className="final-actions">
          <button
            className="final-primary-btn"
            onClick={() => navigate("/mypage")}
          >
            마이페이지에 저장
          </button>
          <button
            className="final-secondary-btn"
            onClick={() => navigate("/")}
          >
            처음으로
          </button>
        </section>
      </div>
    </div>
  );
}

export default FinalPage;
