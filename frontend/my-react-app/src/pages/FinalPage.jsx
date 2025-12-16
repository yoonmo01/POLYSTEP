// frontend/my-react-app/src/pages/FinalPage.jsx
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
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
  const { policyId } = useParams();

  const [policy, setPolicy] = useState(null);
  const [verification, setVerification] = useState(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = localStorage.getItem("access_token");

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

  const navPath = Array.isArray(verification?.navigation_path)
    ? verification.navigation_path
    : [];

  const evidenceText = verification?.evidence_text || "";

  const artifacts = useMemo(() => {
    const arr = ec?.artifacts_extracted || [];
    return Array.isArray(arr) ? arr : [];
  }, [ec]);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        setError("");

        const headers = {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };

        const [policyRes, verifyRes] = await Promise.all([
          fetch(`${API_BASE}/policies/${policyId}`, {
            method: "GET",
            headers,
            credentials: "include",
          }),
          fetch(`${API_BASE}/policies/${policyId}/verification`, {
            method: "GET",
            headers,
            credentials: "include",
          }),
        ]);

        if (policyRes.status === 401 || verifyRes.status === 401) {
          throw new Error("Not authenticated");
        }
        if (!policyRes.ok) throw new Error("정책 정보를 불러올 수 없습니다.");
        if (!verifyRes.ok) throw new Error("검증 결과를 불러올 수 없습니다.");

        const policyData = await policyRes.json();
        const verifyData = await verifyRes.json();

        setPolicy(policyData);
        setVerification(verifyData);
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

  if (!policy || !verification) {
    return (
      <div className="final-page">
        <div className="final-shell">
          <div className="final-section-card">데이터가 없습니다.</div>
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

  return (
    <div className="final-page">
      <div className="final-shell">
        <header className="final-header">
          {/* ✅ STEP 3 글씨 키우기 */}
          <span className="final-step final-step-big">STEP 3 · 최종 추천</span>
          <h1 className="final-title final-title-big">{policy.title}</h1>
          <p className="final-subtitle">자동 검증 결과를 바탕으로 신청 절차를 정리했어요</p>

          {/* ✅ 검증 상태: 초록 SUCCESS pill */}
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

        <div className="final-main">
          {/* ✅ 신청 요약 (더 보기 좋게) */}
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
                <div className="hero-value">
                  {whereToApply ? whereToApply : "상세 내용 확인"}
                </div>
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

          {/* ✅ 자격 요건 */}
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

          {/* ✅ 신청 절차 */}
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

          {/* ✅ 필요 서류 */}
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

          {/* ✅ 추출된 파일/아티팩트: 펼치기 없이 바로 */}
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

          {/* ✅ 검증 근거: 펼치기 없이 바로 */}
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

          {/* ✅ 탐색 경로: 펼치기 없이 바로 */}
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

          {/* ✅ 액션 */}
          <section className="final-actions">
            <button className="final-primary-btn" onClick={() => navigate("/mypage")}>
              마이페이지에 저장
            </button>
            <button className="final-secondary-btn" onClick={() => navigate("/")}>
              처음으로
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}

export default FinalPage;
