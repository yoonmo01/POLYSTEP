import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import "./ResultPage.css";

// base64 헤더로 대충 MIME 추정 (png/jpg/webp 정도만)
const guessMimeFromB64 = (b64) => {
  if (!b64) return "image/jpeg";
  if (b64.startsWith("iVBOR")) return "image/png";
  if (b64.startsWith("UklGR")) return "image/webp";
  if (b64.startsWith("/9j/")) return "image/jpeg";
  return "image/jpeg";
};

const fmtDate = (yyyymmdd) => {
  if (!yyyymmdd) return "-";
  const s = String(yyyymmdd);
  if (s.length !== 8) return s;
  return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
};

const fmtAge = (min, max) => {
  if (min == null && max == null) return "연령 제한 정보 없음";
  if (min != null && max != null) return `만 ${min}~${max}세`;
  if (min != null) return `만 ${min}세 이상`;
  return `만 ${max}세 이하`;
};

const badgeLabel = (s) => {
  if (s === "PASS") return "PASS";
  if (s === "WARNING") return "WARNING";
  if (s === "FAIL") return "FAIL";
  return s || "-";
};

const badgeStyle = (s) => {
  const base = {
    padding: "0.25rem 0.55rem",
    borderRadius: 999,
    fontSize: "0.75rem",
    fontWeight: 800,
    letterSpacing: "0.02em",
    border: "1px solid rgba(148, 163, 184, 0.35)",
    background: "rgba(148, 163, 184, 0.12)",
    color: "#e5e7eb",
    whiteSpace: "nowrap",
  };
  if (s === "PASS")
    return {
      ...base,
      border: "1px solid rgba(34,197,94,0.45)",
      background: "rgba(34,197,94,0.14)",
    };
  if (s === "WARNING")
    return {
      ...base,
      border: "1px solid rgba(245,158,11,0.5)",
      background: "rgba(245,158,11,0.14)",
    };
  if (s === "FAIL")
    return {
      ...base,
      border: "1px solid rgba(239,68,68,0.55)",
      background: "rgba(239,68,68,0.14)",
    };
  return base;
};

// =========================
// ✅ "검색에 사용된 정보" 태그 그룹(색상 구분용)
// =========================
const BASIC_KEYS = new Set(["age", "region"]);
const SCHOLARSHIP_KEYS = new Set([
  "is_student",
  "academic_status",
  "major",
  "grade",
  "gpa",
]);

const tagClassByKey = (key) => {
  if (BASIC_KEYS.has(key)) return "result-tag tag-basic";
  if (SCHOLARSHIP_KEYS.has(key)) return "result-tag tag-scholarship";
  return "result-tag tag-basic";
};

const fitLabel = (s) => {
  if (s === "PASS") return "적합";
  if (s === "WARNING") return "확인 필요";
  if (s === "FAIL") return "부적합";
  return s || "-";
};

function ResultPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const [me, setMe] = useState(null);

  // ✅ ResultPage 진입 state 정규화 (QuestionPage / MyPage 둘 다 대응)
  const incoming = useMemo(() => {
    const st = location.state || {};

    // ✅ MyPage에서 넘어온 경우
    if (st?.from === "mypage" && st?.mode) {
      if (st.mode === "session" && st.session) {
        const sess = st.session;
        const items = Array.isArray(sess?.items) ? sess.items : [];
        const scholarships = Array.isArray(sess?.scholarships)
          ? sess.scholarships.filter(Boolean)
          : sess?.scholarship && typeof sess.scholarship === "object"
          ? [sess.scholarship]
          : Array.isArray(sess?.items)
          ? sess.items.map((x) => x?.scholarship).filter(Boolean)
          : [];

        return {
          conditions: sess?.conditions || null,
          results: items,
          scholarships,
        };
      }

      if (st.mode === "batch" && st.batch) {
        const b = st.batch;
        const policies = Array.isArray(b?.policies) ? b.policies : [];
        const scholarships = Array.isArray(b?.scholarships)
          ? b.scholarships.filter(Boolean)
          : b?.scholarship && typeof b.scholarship === "object"
          ? [b.scholarship]
          : [];

        return {
          conditions: b?.conditions || null,
          results: policies,
          scholarships,
        };
      }
    }

    // ✅ 기존 흐름(QuestionPage → ResultPage)
    return {
      conditions: st?.conditions || null,
      results: Array.isArray(st?.results) ? st.results : [],
      scholarships: Array.isArray(st?.scholarships) ? st.scholarships : [],
    };
  }, [location.state]);

  const conditions = incoming.conditions;
  const incomingResults = incoming.results;
  const incomingScholarships = incoming.scholarships;

  // ✅ UI는 최대 6개, 저장은 Top5
  const results = useMemo(() => incomingResults.slice(0, 6), [incomingResults]);
  const top5ForSave = useMemo(
    () => incomingResults.slice(0, 5),
    [incomingResults]
  );

  const [selected, setSelected] = useState(results[0] || null);
  const [selectedScholarship, setSelectedScholarship] = useState(
    incomingScholarships[0] || null
  );

  const [verifyLogs, setVerifyLogs] = useState([]);
  const [isVerifying, setIsVerifying] = useState(false);

  const [liveImageB64, setLiveImageB64] = useState("");
  const [liveImageMime, setLiveImageMime] = useState("image/jpeg");
  const [finalUrl, setFinalUrl] = useState("");

  const wsRef = useRef(null);

  // ✅ “저장 1회만”
  const savedRecoRef = useRef(false);

  const logBoxRef = useRef(null);
  const [autoScroll, setAutoScroll] = useState(true);

  // ✅ policy_id 방어 (어떤 응답은 id로 올 수도 있음)
  const getPolicyId = (r) => {
    const v = r?.policy_id ?? r?.id ?? null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };

  // =========================
  // ✅ 화면 표시용 사용자 정보 (/me)
  // =========================
  const visibleMeEntries = useMemo(() => {
    if (!me) return [];
    const EXCLUDE_KEYS = new Set(["id", "email", "name", "created_at"]);
    return Object.entries(me).filter(
      ([key, value]) =>
        !EXCLUDE_KEYS.has(key) &&
        value !== null &&
        value !== undefined &&
        value !== ""
    );
  }, [me]);

  const USER_LABEL_MAP = {
    age: "나이",
    region: "거주지",
    is_student: "학생 여부",
    academic_status: "학적 상태",
    major: "전공",
    grade: "학년",
    gpa: "학점",
  };

  useEffect(() => {
    apiFetch("/me")
      .then((data) => setMe(data))
      .catch((e) => console.warn("/me fetch failed:", e?.message));
  }, []);

  useEffect(() => {
    setSelected(results[0] || null);
  }, [results]);

  useEffect(() => {
    setSelectedScholarship(incomingScholarships[0] || null);
  }, [incomingScholarships]);

  // ✅ (MyPage/DB용) ResultPage 진입 시 1회 저장: 정책 + 장학금 같이 저장
  useEffect(() => {
    if (savedRecoRef.current) return;
    if (!conditions) return;
    if (!Array.isArray(top5ForSave) || top5ForSave.length === 0) return;

    savedRecoRef.current = true;

    // 1) DB 저장
    apiFetch("/me/recommendations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conditions,
        results: top5ForSave
          .map((r) => ({
            policy_id: getPolicyId(r),
            badge_status: r.badge_status ?? null,
            score: r.score ?? null,
          }))
          .filter((x) => x.policy_id != null),
        scholarships: incomingScholarships ?? [],
      }),
    }).catch((e) => {
      console.warn("recommendation save failed:", e?.message);
    });

    // 2) localStorage fallback 저장
    try {
      const k = "polystep_recent_result_batches";
      const raw = localStorage.getItem(k);
      const parsed = raw ? JSON.parse(raw) : [];
      const arr = Array.isArray(parsed) ? parsed : [];

      const batch = {
        created_at: new Date().toISOString(),
        scholarships: incomingScholarships ?? [], // ✅ 여러개 저장
        policies: top5ForSave.map((p) => ({
          id: p.id ?? null,
          policy_id: p.policy_id ?? p.id ?? null,
          title: p.title,
          region: p.region,
          category_l: p.category_l,
          category_m: p.category_m,
          badge_status: p.badge_status ?? null,
          score: p.score ?? null,
        })),
        conditions,
      };

      const next = [batch, ...arr].slice(0, 200);
      localStorage.setItem(k, JSON.stringify(next));
    } catch {
      // ignore
    }
  }, [conditions, top5ForSave, incomingScholarships]);

  // 기본 iframe: 정책 자체 URL(있으면)
  const iframeSrc = useMemo(() => {
    if (!selected) return "";
    return finalUrl || selected.target_url || selected.url || "";
  }, [selected, finalUrl]);

  const pushLog = (msg) => {
    const ts = new Date().toLocaleTimeString("ko-KR", { hour12: false });
    setVerifyLogs((prev) => [...prev, `[${ts}] ${msg}`]);
  };

  useEffect(() => {
    if (!autoScroll) return;
    const el = logBoxRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [verifyLogs, autoScroll]);

  const handleLogScroll = () => {
    const el = logBoxRef.current;
    if (!el) return;
    const threshold = 24;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
    setAutoScroll(atBottom);
  };

  const closeWS = () => {
    try {
      if (wsRef.current) wsRef.current.close();
    } catch {}
    wsRef.current = null;
  };

  useEffect(() => {
    return () => closeWS();
  }, []);

  const handleVerify = () => {
    if (!selected) return;
    if (isVerifying) return;

    setIsVerifying(true);
    setVerifyLogs([]);
    setLiveImageB64("");
    setFinalUrl("");

    pushLog(`검증 시작: "${selected.title}" (policy_id=${selected.policy_id})`);

    const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const wsBase = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
    const wsUrl = `${wsBase}/policies/ws/${selected.policy_id}/verify`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => pushLog("WebSocket 연결됨. 브라우저 자동 검증을 시작합니다...");

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);

        if (data.type === "log") {
          pushLog(data.message);
          return;
        }

        if (data.type === "screenshot") {
          const b64 = data.image_b64 || data.image || "";
          if (b64) {
            setLiveImageB64(b64);
            setLiveImageMime(guessMimeFromB64(b64));
          }
          return;
        }

        if (data.type === "done") {
          if (data.status === "SUCCESS") {
            pushLog("검증 완료 ✅");

            // ✅ API views 저장 (+ 장학금도 같이)
            apiFetch("/me/views", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                policy_id: selected?.policy_id,
                verification_id: data.verification_id ?? null,
                scholarship: selectedScholarship || null,
              }),
            }).catch((e) => console.warn("view save failed:", e?.message));

            if (data.final_url) {
              pushLog("최종 페이지 URL 확인됨 → iframe으로 전환");
              setFinalUrl(data.final_url);
            } else {
              pushLog("최종 페이지 URL이 없어서 화면 스트리밍만 표시됩니다.");
            }
          } else {
            pushLog(`검증 실패 ❌: ${data.error || "unknown error"}`);
          }
          setIsVerifying(false);
          closeWS();
          return;
        }

        if (data.type === "error") {
          pushLog(`오류: ${data.message || "unknown error"}`);
          setIsVerifying(false);
          closeWS();
          return;
        }
      } catch {
        // ignore
      }
    };

    ws.onerror = () => {
      pushLog("WebSocket 에러 발생");
      setIsVerifying(false);
      closeWS();
    };

    ws.onclose = () => {
      pushLog("WebSocket 종료");
      setIsVerifying(false);
      wsRef.current = null;
    };
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
              onClick={() =>
                navigate(`/final/${selected?.policy_id}`, {
                  state: { selectedScholarship },
                })
              }
              disabled={!selected}
            >
              POLYSTEP Final Report →
            </button>
          </div>
        </header>

        {(me || conditions) && (
          <section
            className="result-list-panel"
            style={{ marginBottom: "1.2rem", padding: "0.6rem 1.2rem 1.2rem" }}
          >
            <div className="list-head">
              <p className="list-count" style={{ margin: "6px 3px 2px 3px" }}>
                검색에 사용된 정보
              </p>
              <p className="list-hint" style={{ margin: "6px 3px 2px 3px" }}>
                (프로필: 나이/거주지) + (조건: 소득/분야/취업상태/특화) 기반으로 추천했어요.
              </p>
            </div>

            <div
              style={{
                marginTop: "0",
                display: "flex",
                flexDirection: "column",
                gap: "0.7rem",
              }}
            >
              {/* 기본정보 */}
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <span className="tag-group-label">기본정보</span>
                {visibleMeEntries
                  .filter(([key]) => BASIC_KEYS.has(key))
                  .map(([key, value]) => {
                    const label = USER_LABEL_MAP[key] || key;
                    let displayValue = value;
                    if (key === "age") displayValue = `${value}세`;
                    return (
                      <span key={`me-basic-${key}`} className={tagClassByKey(key)}>
                        {label}: {displayValue}
                      </span>
                    );
                  })}
              </div>

              {/* 장학금정보 */}
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <span className="tag-group-label">장학금정보</span>
                {visibleMeEntries
                  .filter(([key]) => SCHOLARSHIP_KEYS.has(key))
                  .map(([key, value]) => {
                    const label = USER_LABEL_MAP[key] || key;
                    let displayValue = value;
                    if (key === "is_student") displayValue = value ? "재학 중" : "비재학";
                    if (key === "gpa") displayValue = `${value} / 4.5`;
                    return (
                      <span key={`me-sch-${key}`} className={"result-tag tag-scholarship"}>
                        {label}: {displayValue}
                      </span>
                    );
                  })}
              </div>

              {/* 정책정보 */}
              <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
                <span className="tag-group-label">정책정보</span>

                {conditions?.income && (
                  <span className="result-tag tag-policy">연소득: {conditions.income}만 원</span>
                )}
                {conditions?.policyField && (
                  <span className="result-tag tag-policy">분야: {conditions.policyField}</span>
                )}
                {conditions?.jobStatus && (
                  <span className="result-tag tag-policy">상태: {conditions.jobStatus}</span>
                )}
                {conditions?.specialField && (
                  <span className="result-tag tag-policy">특화: {conditions.specialField}</span>
                )}
              </div>
            </div>
          </section>
        )}

        <div className="result-layout-3col">
          {/* LEFT: 장학금 */}
          <section className="result-list-panel scholarship-panel scroll-panel">
            <div className="list-head">
              <p className="list-count">🎓 추천 장학금</p>
              <p className="list-hint" style={{ marginTop: 0 }}>
                학적/전공/성적/키워드 기반 장학금 추천이에요.
              </p>
            </div>

            <div className="result-list scroll-body">
              {incomingScholarships.length === 0 ? (
                <div className="detail-empty">조건에 맞는 장학금 추천이 없어요.</div>
              ) : (
                incomingScholarships.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={
                      "result-card scholarship-card" +
                      (selectedScholarship?.id === s.id ? " result-card-active" : "")
                    }
                    onClick={() => setSelectedScholarship(s)}
                    style={{ textAlign: "left" }}
                  >
                    <div className="result-card-main">
                      <div className="result-card-headrow">
                        <h2 className="result-card-title" style={{ margin: 0 }}>
                          {s.name}
                        </h2>
                        <div style={{ display: "flex", gap: "0.45rem", alignItems: "center" }}>
                          {s.category && <span className="result-score-pill">{s.category}</span>}
                          {s.user_fit && (
                            <span style={badgeStyle(s.user_fit)}>{fitLabel(s.user_fit)}</span>
                          )}
                        </div>
                      </div>

                      <p className="result-card-meta">
                        <span>장학금</span>
                        <span>·</span>
                        <span>{s.source_url ? "출처 있음" : "출처 없음"}</span>
                      </p>

                      <p
                        className="result-card-desc"
                        style={{
                          display: "-webkit-box",
                          WebkitLineClamp: 3,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {s.llm_card?.one_liner ||
                          s.selection_criteria ||
                          "장학금 요약 정보 없음"}
                      </p>

                      {(s.user_fit_reason || (s.missing_info && s.missing_info.length > 0)) && (
                        <p
                          className="result-card-meta"
                          style={{ marginTop: "0.55rem", lineHeight: 1.4, opacity: 0.92 }}
                        >
                          {s.user_fit_reason ? <span>🧩 {s.user_fit_reason}</span> : null}
                          {s.missing_info && s.missing_info.length > 0 ? (
                            <>
                              {s.user_fit_reason ? <span> · </span> : null}
                              <span>
                                부족: {s.missing_info.slice(0, 3).join(", ")}
                                {s.missing_info.length > 3 ? "…" : ""}
                              </span>
                            </>
                          ) : null}
                        </p>
                      )}
                    </div>

                    <div className="result-card-bottom">
                      <div className="result-tags">
                        {(s.llm_card?.benefit_summary || s.benefit) && (
                          <span className="result-tag">
                            지급: {s.llm_card?.benefit_summary || s.benefit}
                          </span>
                        )}
                        {s.llm_card?.gpa_min != null && (
                          <span className="result-tag">학점 ≥ {s.llm_card.gpa_min}</span>
                        )}
                        {Array.isArray(s.llm_card?.eligibility_bullets) &&
                          s.llm_card.eligibility_bullets.length > 0 && (
                            <span className="result-tag">조건: {s.llm_card.eligibility_bullets[0]}</span>
                          )}
                      </div>

                      {s.source_url ? (
                        <a
                          href={s.source_url}
                          target="_blank"
                          rel="noreferrer"
                          className="row-link-btn"
                          style={{ textDecoration: "none" }}
                        >
                          보기 →
                        </a>
                      ) : (
                        <span className="row-link-btn" style={{ opacity: 0.6 }}>
                          보기 →
                        </span>
                      )}
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* MIDDLE: 정책 */}
          <section className="result-list-panel policy-panel scroll-panel">
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
                <p className="list-count">
                  총 <strong>{results.length}</strong>개의 추천 정책
                </p>
                <p className="list-hint" style={{ marginTop: 0 }}>
                  카드를 클릭하면 오른쪽에서 정책 페이지/실시간 검증 화면을 볼 수 있어요.
                </p>
              </div>

              <button
                type="button"
                className="result-next-btn"
                onClick={handleVerify}
                disabled={isVerifying || !selected}
              >
                {isVerifying ? "검증 중..." : "검증하기"}
              </button>
            </div>

            <div className="result-list scroll-body">
              {results.length === 0 ? (
                <div className="detail-empty">
                  추천 결과가 없어요. 조건을 바꿔 다시 시도해 주세요.
                </div>
              ) : (
                results.map((item) => (
                  <button
                    key={item.policy_id ?? item.id}
                    type="button"
                    className={
                      "result-card" +
                      (selected?.policy_id === item.policy_id ? " result-card-active" : "")
                    }
                    onClick={() => {
                      setSelected(item);
                      setFinalUrl("");
                      setLiveImageB64("");
                      setVerifyLogs([]);
                      setIsVerifying(false);
                      closeWS();
                    }}
                  >
                    <div className="result-card-main">
                      <div className="result-card-headrow">
                        <h2 className="result-card-title" style={{ margin: 0 }}>
                          {item.title}
                        </h2>
                        <div className="result-card-badges">
                          <span style={badgeStyle(item.badge_status)}>
                            {badgeLabel(item.badge_status)}
                          </span>

                          {item.has_verification_cache ? (
                            <span
                              className="verify-badge verify-done"
                              title={
                                item.last_verified_at
                                  ? `마지막 검증: ${item.last_verified_at}`
                                  : "검증됨"
                              }
                            >
                              ✔ 검증됨
                            </span>
                          ) : (
                            <span className="verify-badge verify-pending">⏳ 미검증</span>
                          )}
                        </div>
                      </div>

                      <p className="result-card-meta">
                        <span>{item.region || "-"}</span>
                        <span>·</span>
                        <span>
                          {[item.category_l, item.category_m].filter(Boolean).join(" / ") ||
                            item.category ||
                            "-"}
                        </span>
                      </p>

                      <p
                        className="result-card-desc"
                        style={{
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        }}
                      >
                        {item.short_summary || "요약 정보가 없습니다."}
                      </p>
                    </div>

                    <div className="result-card-bottom">
                      <div className="result-tags">
                        <span className="result-tag">연령: {fmtAge(item.age_min, item.age_max)}</span>
                        <span className="result-tag">모집: {item.apply_period_type || "-"}</span>
                        <span className="result-tag">마감: {fmtDate(item.biz_end)}</span>
                      </div>

                      <span className="result-score-pill">추천 정책</span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </section>

          {/* RIGHT: iframe/실시간 */}
          <section className="result-detail-panel detail-panel">
            <div className="detail-card" style={{ height: "100%" }}>
              <div className="detail-iframe-block" style={{ width: "100%", height: "100%", minHeight: 520 }}>
                {isVerifying ? (
                  <div style={{ height: "100%", display: "flex", flexDirection: "column", gap: "0.8rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "0.8rem" }}>
                      <div style={{ fontWeight: 800, color: "#e5e7eb" }}>브라우저 자동 탐색 화면</div>
                      <button
                        type="button"
                        className="result-back-btn"
                        onClick={() => {
                          pushLog("사용자 요청으로 검증 중지");
                          closeWS();
                          setIsVerifying(false);
                        }}
                      >
                        중지
                      </button>
                    </div>

                    <div
                      style={{
                        flex: 1,
                        borderRadius: 14,
                        border: "1px solid rgba(148, 163, 184, 0.35)",
                        background: "rgba(2, 6, 23, 0.55)",
                        overflow: "hidden",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minHeight: 480,
                      }}
                    >
                      {liveImageB64 ? (
                        <img
                          src={`data:${liveImageMime};base64,${liveImageB64}`}
                          alt="live"
                          style={{ width: "100%", height: "100%", objectFit: "contain" }}
                        />
                      ) : (
                        <div style={{ color: "#9ca3af", fontSize: "0.9rem" }}>
                          화면 로딩 중... (첫 스크린샷 대기)
                        </div>
                      )}
                    </div>
                  </div>
                ) : iframeSrc ? (
                  <iframe
                    src={iframeSrc}
                    title={selected?.title || "policy"}
                    className="result-iframe"
                    loading="lazy"
                    style={{ height: "100%", borderRadius: 14 }}
                  />
                ) : (
                  <div className="detail-empty">
                    정책 URL이 아직 없어요.
                    <div style={{ marginTop: "0.7rem", fontSize: "0.9rem", opacity: 0.9 }}>
                      현재 선택: <strong>{selected?.title || "-"}</strong>
                      <br />
                      policy_id: <strong>{selected?.policy_id || "-"}</strong>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* BOTTOM: 로그 */}
        <section className="result-list-panel log-panel">
          {/* ✅ 헤더 정렬은 class로 제어 */}
          <div className="list-head log-head">
            <div>
              <p className="list-count" style={{ marginBottom: 4 }}>
                검증 로그
              </p>
              <p className="list-hint" style={{ marginTop: 0 }}>
                백엔드 브라우저 자동 탐색 과정을 실시간으로 보여줍니다.
              </p>
            </div>

            <div className="log-actions">
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

          {/* ✅ 로그 박스도 class로 제어 */}
          <div ref={logBoxRef} onScroll={handleLogScroll} className="log-box">
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
