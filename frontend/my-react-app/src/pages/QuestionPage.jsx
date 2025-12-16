//frontend/my-react-app/src/pages/QuestionPage.jsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./QuestionPage.css";
import { getUser } from "../auth";

function QuestionPage() {
  const navigate = useNavigate();

  // 상태 관리
  const [income, setIncome] = useState("");
  const [policyField, setPolicyField] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [specialField, setSpecialField] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");

  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

  // 버튼 옵션들 (나중에 DB 기준에 맞게 텍스트만 수정하면 됨)
  const policyOptions = [
    "생활",
    "주거",
    "교육",
    "일자리",
    "창업",
    "금융",
    "문화",
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

  const handleSubmit = async (e) => {
    e.preventDefault();

    // 간단한 유효성 검사
    if (!income || !policyField || !jobStatus) {
      alert("연소득, 정책 분야, 취업 상태는 최소 한 번씩 선택해 주세요.");
      return;
    }

    if (isLoading) return;

    // ✅ 백엔드 PolicySearchRequest가 query/age/region/category라서 매핑
    const user = getUser();
    if (!user) {
      alert("로그인이 필요합니다.");
      navigate("/login");
      return;
    }

    const userProfile = {
      name: user.name,
      email: user.email,
      age: user.age ? Number(user.age) : undefined,
      region: user.region,
    };

    // ✅ income/jobStatus/specialField는 query에 녹여서 전달(임시 매핑)
    const searchConditions = {
      income,
      policyField,
      jobStatus,
      specialField,
    };

    const query = [
      `소득:${income}만원`,
      `취업상태:${jobStatus}`,
      `특화:${specialField || "없음"}`,
    ].join(" | ");;

    const qs = new URLSearchParams();
    if (query) qs.set("query", query);
    if (userProfile.age !== undefined) qs.set("age", String(userProfile.age));
    if (userProfile.region) qs.set("region", userProfile.region);
    if (policyField) qs.set("category", policyField);

    setIsLoading(true);
    setLoadingMsg("정책을 찾는 중이에요...");

    // 로딩 메시지 단계별로 바꿔주기(UX)
    const t1 = setTimeout(() => setLoadingMsg("조건에 맞는 정책을 분석 중이에요..."), 700);
    const t2 = setTimeout(() => setLoadingMsg("유사한 정책을 묶어서 정리하는 중이에요..."), 1500);
    const t3 = setTimeout(() => setLoadingMsg("거의 다 됐어요. 결과를 불러오는 중!"), 2300);

    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`${API_BASE_URL}/policies/search_with_similar?${qs.toString()}`, {
        method: "GET",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });

      const data = await res.json().catch(() => null);
      if (!res.ok) {
        const msg = data?.detail || "정책 검색에 실패했습니다.";
        throw new Error(msg);
      }

      // ✅ 응답에서 기준 1개 + 유사 정책들 합치고, "최대 5개만" 보여주기
      const base = data?.base_policy ? [data.base_policy] : [];
      const similars = Array.isArray(data?.similar_policies) ? data.similar_policies : [];
      const merged = [...base, ...similars];
      const top5 = merged.slice(0, 5);

      if (top5.length === 0) {
        alert("조건에 맞는 정책을 찾지 못했어요. 조건을 바꿔 다시 시도해 주세요.");
        return;
      }

      navigate("/result", {
        state: {
          user: userProfile,
          conditions: searchConditions,
          results: top5,
        },
      });
    } catch (err) {
      // 401이면 로그인 유도
      if (String(err?.message || "").includes("401") || String(err?.message || "").includes("Not authenticated")) {
        alert("로그인이 필요합니다. 로그인 후 다시 시도해 주세요.");
        navigate("/login");
        return;
      }
      alert(err.message || "알 수 없는 오류가 발생했습니다.");
    } finally {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setIsLoading(false);
      setLoadingMsg("");
    }
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

        {/* ✅ 로딩 오버레이 */}
        {isLoading && (
          <div
            style={{
              position: "fixed",
              inset: 0,
              background: "rgba(2, 6, 23, 0.55)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 9999,
              padding: "1.2rem",
            }}
          >
            <div
              style={{
                width: "min(520px, 92vw)",
                background: "rgba(15, 23, 42, 0.92)",
                border: "1px solid rgba(148, 163, 184, 0.25)",
                borderRadius: 16,
                padding: "1.2rem 1.1rem",
                color: "#e5e7eb",
                boxShadow: "0 10px 30px rgba(0,0,0,0.35)",
              }}
            >
              <div style={{ display: "flex", gap: "0.9rem", alignItems: "center" }}>
                <div
                  aria-label="loading"
                  style={{
                    width: 18,
                    height: 18,
                    borderRadius: "50%",
                    border: "3px solid rgba(148, 163, 184, 0.35)",
                    borderTopColor: "rgba(229, 231, 235, 0.95)",
                    animation: "polystepSpin 0.85s linear infinite",
                    flexShrink: 0,
                  }}
                />
                <div>
                  <p style={{ margin: 0, fontWeight: 700, fontSize: "1rem" }}>{loadingMsg || "불러오는 중..."}</p>
                  <p style={{ margin: "0.35rem 0 0", color: "rgba(226,232,240,0.8)", fontSize: "0.9rem" }}>
                    잠시만 기다려 주세요. (검색/유사도 계산 중)
                  </p>
                </div>
              </div>
            </div>

            {/* keyframes */}
            <style>{`@keyframes polystepSpin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}

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

            <button type="submit" className="question-submit-btn" disabled={isLoading}>
              {isLoading ? "정책 찾는 중..." : "이 조건으로 정책 추천 받기"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}

export default QuestionPage;
