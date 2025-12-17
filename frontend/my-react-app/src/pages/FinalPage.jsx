// frontend/my-react-app/src/pages/FinalPage.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import "./FinalPage.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const fmtIso = (iso) => {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("ko-KR", { hour12: false });
  } catch {
    return iso;
  }
};

const safeDecode = (v) => {
  if (!v) return "";
  try {
    return decodeURIComponent(String(v));
  } catch {
    return String(v);
  }
};

const isHttpUrl = (v) => typeof v === "string" && /^https?:\/\//i.test(v);

const prettyJson = (obj) => {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
};

const labelMap = {
  age: "나이",
  region: "거주/지역",
  income: "소득",
  employment: "취업/상태",
  other: "기타 조건",
};

const statusLabel = (s) => {
  if (!s) return "-";
  if (s === "SUCCESS") return "SUCCESS";
  if (s === "FAIL") return "FAIL";
  if (s === "RUNNING") return "RUNNING";
  return String(s);
};

const statusClass = (s) => {
  const v = String(s || "").toLowerCase();
  if (v.includes("success")) return "success";
  if (v.includes("fail")) return "fail";
  if (v.includes("running") || v.includes("progress")) return "running";
  return "default";
};

function FinalPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { policyId } = useParams();

  const [policy, setPolicy] = useState(null);
  const [verification, setVerification] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = localStorage.getItem("access_token");

  const selectedScholarship = location.state?.selectedScholarship || null;
  const sc = selectedScholarship?.llm_card || null;

  // ✅ "페이지 단위 1회" 보장용 (state 대신 ref)
  const localViewPostedRef = useRef(false);
  const viewPostedRef = useRef(false);

  const ec = verification?.extracted_criteria || {};
  const fg = ec?.final_guidance || null;

  const applyChannel = fg?.apply_overview?.apply_channel || ec?.apply_channel || "-";
  const applyPeriod = fg?.apply_overview?.apply_period || ec?.apply_period || "-";
  const whereToApply = fg?.apply_overview?.where_to_apply || "";
  const contact = fg?.contact || ec?.contact || null;

  const criteria = fg?.eligibility || ec?.criteria || {};
  const applySteps = fg?.final_apply_steps || ec?.apply_steps || [];
  const requiredDocs = fg?.final_required_documents || ec?.required_documents || [];

  const status = verification?.status || "-";
  const lastVerifiedAt = verification?.last_verified_at || "";

  const navPath = Array.isArray(verification?.navigation_path) ? verification.navigation_path : [];
  const evidenceText = verification?.evidence_text || "";

  // ✅ 저장용: verification id 추정(백엔드 키 이름이 다를 수 있어서 방어적으로)
  const verificationId = verification?.verification_id ?? verification?.id ?? verification?._id ?? null;

  const artifacts = useMemo(() => {
    const arr = ec?.artifacts_extracted || [];
    return Array.isArray(arr) ? arr : [];
  }, [ec]);

  // ✅ localStorage “최근 본(정책+장학금)” 기록
  const pushLocalRecentView = (payload) => {
    try {
      const key = "polystep_recent_views";
      const raw = localStorage.getItem(key);
      const prev = raw ? JSON.parse(raw) : [];
      const arr = Array.isArray(prev) ? prev : [];

      const policyKey = String(payload?.policy_id ?? "");
      const schKey = String(payload?.scholarship?.id ?? payload?.scholarship?.name ?? "");

      const next = arr.filter((x) => {
        const samePolicy = String(x?.policy_id ?? "") === policyKey;
        const sameSch = String(x?.scholarship?.id ?? x?.scholarship?.name ?? "") === schKey;
        return !(samePolicy && sameSch);
      });

      next.unshift(payload);
      localStorage.setItem(key, JSON.stringify(next.slice(0, 10)));
    } catch (e) {
      console.warn("pushLocalRecentView failed:", e?.message);
    }
  };

  // ✅ (임시) Final 저장: 정책 + 장학금을 함께 저장 (MyPage “저장 목록” 용도)
  const handleSaveFinal = async () => {
    try {
      const payload = {
        saved_at: new Date().toISOString(),
        policy_id: Number(policyId),
        verification_id: verificationId,
        policy_title: policy?.title || "",
        scholarship: selectedScholarship || null,
      };

      const key = "polystep_saved_finals";
      const prevRaw = localStorage.getItem(key);
      const prev = prevRaw ? JSON.parse(prevRaw) : [];
      const next = Array.isArray(prev) ? prev : [];

      const schId = selectedScholarship?.id ?? null;
      const filtered = next.filter((x) => {
        const samePolicy = String(x?.policy_id) === String(payload.policy_id);
        const sameSch = String(x?.scholarship?.id ?? "") === String(schId ?? "");
        return !(samePolicy && sameSch);
      });

      filtered.unshift(payload);
      localStorage.setItem(key, JSON.stringify(filtered));

      navigate("/mypage", { state: { savedFinal: payload } });
    } catch (e) {
      console.warn("final save failed:", e?.message);
      navigate("/mypage");
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError("");

        const headers = {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        // ✅ verification이 404일 수 있으니 분리 처리
        const policyRes = await fetch(`${API_BASE}/policies/${policyId}`, {
          method: "GET",
          headers,
          credentials: "include",
        });

        if (policyRes.status === 401) throw new Error("Not authenticated");
        if (!policyRes.ok) throw new Error("정책 정보를 불러올 수 없습니다.");

        let verifyRes = null;
        try {
          verifyRes = await fetch(`${API_BASE}/policies/${policyId}/verification`, {
            method: "GET",
            headers,
            credentials: "include",
          });
        } catch {
          verifyRes = null;
        }

        const policyData = await policyRes.json();
        const normalizedPolicy = policyData?.policy ?? policyData;

        // ✅ verification은 없을 수도 있음(404)
        let normalizedVerification = null;
        if (verifyRes) {
          if (verifyRes.status === 401) throw new Error("Not authenticated");
          if (verifyRes.ok) {
            const verifyData = await verifyRes.json();
            normalizedVerification = verifyData?.verification ?? verifyData;
          } else {
            // 404면 그냥 null 유지
            normalizedVerification = null;
          }
        }

        setPolicy(normalizedPolicy);
        setVerification(normalizedVerification);
      } catch (e) {
        const msg = String(e?.message || "");
        if (msg.includes("Not authenticated") || msg.includes("401")) {
          setError("로그인이 필요합니다. 로그인 후 다시 시도해 주세요.");
          return;
        }
        setError(e?.message || "데이터 로딩 실패");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [policyId, token]);

  // ✅ FinalPage "보기만 해도" localStorage(최근 본: 정책+장학금) 기록
  useEffect(() => {
    try {
      if (!policy) return;
      if (!policyId) return;
      if (localViewPostedRef.current) return;

      const payload = {
        viewed_at: new Date().toISOString(),
        policy_id: Number(policyId),
        policy_title: policy?.title || "",
        policy_region: policy?.region || null,
        policy_category:
          [policy?.category_l, policy?.category_m].filter(Boolean).join(" / ") ||
          policy?.category ||
          null,
        verification_id: verificationId ?? null,
        verification_status: verification?.status || null,
        scholarship: selectedScholarship || null,
      };

      pushLocalRecentView(payload);
      localViewPostedRef.current = true;
    } catch (e) {
      console.warn("local recent view save failed:", e?.message);
    }
  }, [policy, verification, policyId, verificationId, selectedScholarship]);

  // ✅ FinalPage "보기"만 해도 최근 본으로 기록 (/me/views)
  useEffect(() => {
    const postView = async () => {
      try {
        if (!token) return;
        if (!policyId) return;
        if (viewPostedRef.current) return;
        if (!policy) return;

        const headers = {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        };

        const body = {
          policy_id: Number(policyId),
          verification_id: verificationId ?? null,
          // ✅ 핵심: 장학금도 같이 저장해서 MyPage 하단 “세트”로 나오게
          scholarship: selectedScholarship || null,
        };

        await fetch(`${API_BASE}/me/views`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify(body),
        });

        viewPostedRef.current = true;
      } catch (e) {
        console.warn("post view failed:", e?.message);
      }
    };

    // ✅ verification 없어도 policy만 있으면 저장 가능
    postView();
  }, [policy, policyId, token, verificationId, selectedScholarship]);

  if (loading) return <div className="final-page">로딩 중...</div>;

  if (error) {
    return (
      <div className="final-page">
        <div className="final-shell">
          <div className="final-section-card">
            <p style={{ color: "#fca5a5", fontWeight: 800, margin: 0 }}>{error}</p>
            <div className="final-actions" style={{ justifyContent: "flex-start" }}>
              {error.includes("로그인") && (
                <button className="final-primary-btn" onClick={() => navigate("/login")}>
                  로그인으로
                </button>
              )}
              <button className="final-secondary-btn" onClick={() => navigate(-1)}>
                뒤로가기
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!policy) {
    return (
      <div className="final-page">
        <div className="final-shell">
          <div className="final-section-card">정책 데이터가 없습니다.</div>
        </div>
      </div>
    );
  }

  const contactText = (() => {
    if (!contact) return "-";
    const org = contact?.org ? String(contact.org) : "";
    const tel = contact?.tel ? String(contact.tel) : "";
    if (org && tel) return `${org} · ${tel}`;
    return org || tel || "-";
  })();

  const policyUrl = policy?.target_url || policy?.source_url || policy?.url || "";

  return (
    <div className="final-page">
      <div className="final-shell">
        <header className="final-header">
          <span className="final-step final-step-big">STEP 3 · 최종 추천</span>
          <h1 className="final-title final-title-big">{policy.title}</h1>
          <p className="final-subtitle">자동 검증 결과를 바탕으로 신청 절차를 정리했어요</p>

          <div className="final-status-row">
            <div className={`verify-pill verify-pill-${statusClass(status)}`}>
              <span className="verify-pill-dot" />
              <span className="verify-pill-text">검증 상태: {statusLabel(status)}</span>
            </div>
            <span className="info-pill">
              <span className="info-label">마지막 검증</span>
              <span className="info-value">{fmtIso(lastVerifiedAt)}</span>
            </span>
          </div>
        </header>

        <div className="final-split">
          {/* LEFT: 장학금 */}
          <aside className="final-left">
            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">🎓 선택한 장학금</h3>
                <span className="final-section-hint">Result에서 선택한 장학금 기준</span>
              </div>

              {!selectedScholarship ? (
                <p className="final-muted">
                  선택된 장학금이 없습니다. ResultPage에서 하나를 선택해 주세요.
                </p>
              ) : (
                <div className="sch-block">
                  <div className="sch-title">
                    {selectedScholarship?.name || "(장학금명 없음)"}
                  </div>

                  <div className="sch-badges">
                    {selectedScholarship?.category ? (
                      <span className="info-pill">
                        <span className="info-label">유형</span>
                        <span className="info-value">{selectedScholarship.category}</span>
                      </span>
                    ) : null}
                    {selectedScholarship?.user_fit ? (
                      <span className="info-pill">
                        <span className="info-label">적합도</span>
                        <span className="info-value">{String(selectedScholarship.user_fit)}</span>
                      </span>
                    ) : null}
                    <span className="info-pill">
                      <span className="info-label">출처</span>
                      <span className="info-value">
                        {selectedScholarship?.source_url ? "있음" : "없음"}
                      </span>
                    </span>
                  </div>

                  <div className="sch-section">
                    <div className="sch-section-title">Gemini 요약</div>
                    <div className="sch-text">
                      {sc?.one_liner ||
                        selectedScholarship?.selection_criteria ||
                        "요약 정보가 없습니다."}
                    </div>
                  </div>

                  {(sc?.benefit_summary || selectedScholarship?.benefit) && (
                    <div className="sch-section">
                      <div className="sch-section-title">지원 내용</div>
                      <div className="sch-text">
                        {sc?.benefit_summary || selectedScholarship?.benefit}
                      </div>
                    </div>
                  )}

                  {Array.isArray(sc?.eligibility_bullets) && sc.eligibility_bullets.length > 0 && (
                    <div className="sch-section">
                      <div className="sch-section-title">지원 자격 (Gemini)</div>
                      <ul className="final-bullet-list" style={{ marginTop: 0 }}>
                        {sc.eligibility_bullets.map((t, i) => (
                          <li key={`${t}-${i}`}>{String(t)}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {Array.isArray(sc?.required_docs) && sc.required_docs.length > 0 && (
                    <div className="sch-section">
                      <div className="sch-section-title">필요 서류 (Gemini)</div>
                      <ul className="final-doc-list" style={{ marginTop: 0 }}>
                        {sc.required_docs.map((d, i) => (
                          <li key={`${d}-${i}`} className="final-doc-item">
                            <span className="final-doc-icon">📄</span>
                            <span>{String(d)}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {sc && (
                    <details className="sch-details">
                      <summary>Gemini 분석 전체(JSON) 보기</summary>
                      <pre className="final-pre final-pre-tight">{prettyJson(sc)}</pre>
                    </details>
                  )}

                  {(selectedScholarship?.raw_text ||
                    selectedScholarship?.raw ||
                    selectedScholarship?.text) && (
                    <div className="sch-section">
                      <div className="sch-section-title">원문 텍스트</div>
                      <pre className="final-pre final-pre-tight">
                        {String(
                          selectedScholarship?.raw_text ||
                            selectedScholarship?.raw ||
                            selectedScholarship?.text
                        )}
                      </pre>
                    </div>
                  )}

                  <details className="sch-details">
                    <summary>전체 원문(JSON) 보기</summary>
                    <pre className="final-pre final-pre-tight">
                      {prettyJson(selectedScholarship)}
                    </pre>
                  </details>

                  {selectedScholarship?.source_url ? (
                    <a
                      className="final-link"
                      href={selectedScholarship.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      장학금 출처 바로가기 →
                    </a>
                  ) : (
                    <div className="final-muted">출처 링크가 없습니다.</div>
                  )}
                </div>
              )}
            </section>
          </aside>

          {/* RIGHT: 정책 */}
          <main className="final-right">
            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">📌 선택한 청년정책</h3>
                <span className="final-section-hint">Result에서 선택한 정책 기준</span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                <div style={{ fontWeight: 900, fontSize: "1.05rem" }}>
                  {policy?.title || "(정책명 없음)"}
                </div>

                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <span className="info-pill">
                    <span className="info-label">지역</span>
                    <span className="info-value">{policy?.region || "-"}</span>
                  </span>
                  <span className="info-pill">
                    <span className="info-label">분류</span>
                    <span className="info-value">
                      {[policy?.category_l, policy?.category_m].filter(Boolean).join(" / ") ||
                        policy?.category ||
                        "-"}
                    </span>
                  </span>
                </div>

                {policyUrl ? (
                  <a className="final-link" href={policyUrl} target="_blank" rel="noreferrer">
                    정책 원문 바로가기 →
                  </a>
                ) : (
                  <div className="final-muted">정책 링크가 없습니다.</div>
                )}
              </div>
            </section>

            <section className="final-hero-card">
              <div className="final-hero-info-grid">
                <div className="hero-item">
                  <div className="hero-label">신청 방식</div>
                  <div className="hero-value">{applyChannel}</div>
                </div>

                <div className="hero-item">
                  <div className="hero-label">신청 기간</div>
                  <div className="hero-value">{applyPeriod}</div>
                </div>

                <div className="hero-item hero-wide">
                  <div className="hero-label">접수</div>
                  <div className="hero-value">{whereToApply ? whereToApply : "상세 내용 확인"}</div>
                </div>

                <div className="hero-item hero-wide">
                  <div className="hero-label">문의</div>
                  <div className="contact-box">
                    <span className="contact-icon">☎</span>
                    <span className="contact-text">{contactText}</span>
                  </div>
                </div>
              </div>
            </section>

            {/* ✅ verification이 없을 수도 있으니 섹션들은 그대로 두되, 데이터 없으면 “없음” 표시되게 기존 로직이 이미 방어적임 */}

            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">자격 요건 요약</h3>
              </div>

              {criteria && Object.keys(criteria).length > 0 ? (
                <ul className="final-bullet-list">
                  {Object.entries(criteria).map(([key, val]) => (
                    <li key={key}>
                      <strong>{labelMap[key] || key}</strong>
                      <span className="final-kv-sep">:</span>
                      <span className="final-kv-val">{String(val || "-")}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="final-muted">자격 요건 정보가 없습니다.</p>
              )}
            </section>

            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">신청 절차</h3>
              </div>

              {Array.isArray(applySteps) && applySteps.length > 0 ? (
                <ol className="final-step-list">
                  {applySteps.map((step) => (
                    <li
                      key={step.step ?? `${step.title}-${step.detail}`}
                      className="final-step-item"
                    >
                      <div className="final-step-top">
                        <span className="final-step-badge">STEP {step.step ?? "-"}</span>
                        <div className="final-step-name">{step.title || "단계"}</div>
                      </div>

                      <p className="final-step-desc">{step.detail || "-"}</p>

                      {step.url && (
                        <a className="final-link" href={step.url} target="_blank" rel="noreferrer">
                          바로가기 →
                        </a>
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="final-muted">신청 절차 정보가 없습니다.</p>
              )}
            </section>

            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">필요 서류</h3>
              </div>

              {Array.isArray(requiredDocs) && requiredDocs.length > 0 ? (
                <ul className="final-doc-list">
                  {requiredDocs.map((doc, idx) => {
                    if (typeof doc === "string") {
                      const decoded = safeDecode(doc);
                      const looksUrl = isHttpUrl(decoded);
                      return (
                        <li key={`${decoded}-${idx}`} className="final-doc-item">
                          <span className="final-doc-icon">📄</span>
                          {looksUrl ? (
                            <a className="final-link" href={decoded} target="_blank" rel="noreferrer">
                              {decoded}
                            </a>
                          ) : (
                            <span>{decoded}</span>
                          )}
                        </li>
                      );
                    }

                    const name = safeDecode(doc?.name || "(서류명 없음)");
                    const note = doc?.note ? String(doc.note) : "";
                    const required = doc?.required === true;

                    return (
                      <li key={`${name}-${idx}`} className="final-doc-item">
                        <span className="final-doc-icon">📄</span>
                        <div className="final-doc-body">
                          <div className="final-doc-title">
                            <strong>{name}</strong>
                            {required && <span className="final-required">필수</span>}
                          </div>
                          {note && <div className="final-doc-note">- {note}</div>}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="final-muted">필요 서류 정보가 없습니다.</p>
              )}
            </section>

            {artifacts.length > 0 && (
              <section className="final-section-card">
                <div className="final-section-head">
                  <h3 className="final-section-title">추출된 파일/아티팩트</h3>
                  <span className="final-section-hint">길면 내부 스크롤로 확인</span>
                </div>

                <div className="final-artifacts">
                  {artifacts.map((a, idx) => (
                    <div key={`${a.name}-${idx}`} className="final-artifact-card">
                      <div className="final-artifact-title">{safeDecode(a.name || "파일")}</div>
                      <div className="final-artifact-meta">
                        source: {a.source_type || "-"} / ext: {a?.meta?.ext || "-"} / pages:{" "}
                        {a?.meta?.pages ?? "-"}
                      </div>

                      {a.text ? (
                        <pre className="final-pre final-pre-tight">{a.text}</pre>
                      ) : (
                        <p className="final-muted" style={{ marginTop: "0.75rem" }}>
                          추출 텍스트가 없습니다.
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">검증 근거</h3>
                <span className="final-section-hint">길면 내부 스크롤로 확인</span>
              </div>

              {evidenceText ? (
                <pre className="final-pre">{evidenceText}</pre>
              ) : (
                <p className="final-muted">근거 텍스트가 없습니다.</p>
              )}
            </section>

            <section className="final-section-card">
              <div className="final-section-head">
                <h3 className="final-section-title">탐색 경로</h3>
                <span className="final-section-hint">길면 내부 스크롤로 확인</span>
              </div>

              <ol className="final-nav-list final-scroll-box">
                {navPath.length === 0 ? (
                  <li>탐색 경로 정보가 없습니다.</li>
                ) : (
                  navPath.map((p, idx) => (
                    <li key={idx} className="final-nav-item">
                      <div className="final-nav-top">
                        <span className="final-nav-action">[{p.action}]</span>
                        <span className="final-nav-label">{p.label}</span>
                        {p.note ? <span className="final-nav-note">· {p.note}</span> : null}
                      </div>
                      {p.url ? (
                        <a className="final-link" href={p.url} target="_blank" rel="noreferrer">
                          {p.url}
                        </a>
                      ) : null}
                    </li>
                  ))
                )}
              </ol>
            </section>

            <section className="final-actions">
              <button className="final-primary-btn" onClick={handleSaveFinal}>
                마이페이지에 저장
              </button>
              <button className="final-secondary-btn" onClick={() => navigate("/")}>
                처음으로
              </button>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}

export default FinalPage;
