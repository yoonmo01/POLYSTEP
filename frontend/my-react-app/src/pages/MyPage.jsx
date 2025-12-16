//frontend/my-react-app/src/pages/MyPage.jsx
import "./MyPage.css";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";

const fmtMaybe = (v) => (v == null || v === "" ? "-" : String(v));

function MyPage() {
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);

  // ✅ 오른쪽 위: API 추천 세션 히스토리
  const [recommendationSessions, setRecommendationSessions] = useState([]);

  // ✅ 왼쪽 아래: API views 히스토리
  const [viewedHistory, setViewedHistory] = useState([]);

  // ✅ 로컬 fallback(추천 묶음)
  const [recentResultBatchesFallback, setRecentResultBatchesFallback] = useState(
    []
  );

  // ✅ 로컬 fallback(views 묶음)
  const [recentViewsFallback, setRecentViewsFallback] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const displayName = useMemo(
    () => profile?.name || profile?.full_name || "사용자",
    [profile]
  );

  const statusClass = (s) => {
    const v = String(s || "").toLowerCase();
    if (v.includes("pass")) return "status-pass";
    if (v.includes("warning")) return "status-warning";
    if (v.includes("success")) return "status-success";
    if (v.includes("fail")) return "status-fail";
    if (v.includes("running") || v.includes("progress") || v.includes("pending"))
      return "status-running";
    return "status-recommend";
  };

  const fmtTime = (iso) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return String(iso);
      return d.toLocaleString("ko-KR", { hour12: false });
    } catch {
      return String(iso);
    }
  };

  // ✅ 응답 형태가 달라도 sessions 배열로 정규화
  const normalizeSessions = (hist) => {
    if (Array.isArray(hist?.sessions)) return hist.sessions;
    if (Array.isArray(hist?.data?.sessions)) return hist.data.sessions;
    if (Array.isArray(hist)) return hist;
    if (Array.isArray(hist?.data)) return hist.data;
    return [];
  };

  // ✅ 응답 형태가 달라도 views(items) 배열로 정규화
  const normalizeViews = (views) => {
    if (Array.isArray(views?.items)) return views.items;
    if (Array.isArray(views?.data?.items)) return views.data.items;
    if (Array.isArray(views)) return views;
    if (Array.isArray(views?.data)) return views.data;
    return [];
  };

  /**
   * ✅ 핵심 수정:
   * "세션의 장학금 전부"를 가져오기
   * - sess.scholarships 가 정석
   * - 예외: sess.scholarship (단일) / items[].scholarship
   */
  const getScholarshipsFromSession = (sess) => {
    if (!sess) return [];

    // 1) { scholarships: [...] }
    if (Array.isArray(sess.scholarships)) return sess.scholarships.filter(Boolean);

    // 2) { scholarship: {...} }
    if (sess.scholarship && typeof sess.scholarship === "object")
      return [sess.scholarship];

    // 3) { items: [{ scholarship: {...} }, ...] }
    if (Array.isArray(sess.items)) {
      const arr = sess.items.map((x) => x?.scholarship).filter(Boolean);
      return arr;
    }

    return [];
  };

  /**
   * ✅ fallback(로컬)에서도 장학금 전부 대응
   * - batch.scholarships (신규)
   * - batch.scholarship (구버전)
   */
  const getScholarshipsFromBatch = (batch) => {
    if (!batch) return [];
    if (Array.isArray(batch.scholarships)) return batch.scholarships.filter(Boolean);
    if (batch.scholarship && typeof batch.scholarship === "object") return [batch.scholarship];
    return [];
  };

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError("");

        // 1) 프로필
        const me = await apiFetch("/me");
        setProfile(me);

        // 2) ✅ 추천 세션 히스토리(API)
        try {
          const hist = await apiFetch("/me/recommendations/history?limit=200");
          const sessions = normalizeSessions(hist);
          setRecommendationSessions(sessions);
        } catch (e) {
          console.warn("recommendation history fetch failed:", e?.message);
          setRecommendationSessions([]);
        }

        // 3) ✅ 최근 본(검증/열람) 히스토리(API)
        try {
          const views = await apiFetch("/me/views?limit=50");
          const items = normalizeViews(views);
          setViewedHistory(items);
        } catch (e) {
          console.warn("views fetch failed:", e?.message);
          setViewedHistory([]);
        }

        // 4) ✅ fallback: ResultPage 저장 추천 묶음
        try {
          const k = "polystep_recent_result_batches";
          const raw = localStorage.getItem(k);
          const parsed = raw ? JSON.parse(raw) : [];
          const arr = Array.isArray(parsed) ? parsed : [];
          setRecentResultBatchesFallback(arr);
        } catch {
          setRecentResultBatchesFallback([]);
        }

        // 5) ✅ fallback: FinalPage 로컬 recent views
        try {
          const k2 = "polystep_recent_views";
          const raw2 = localStorage.getItem(k2);
          const parsed2 = raw2 ? JSON.parse(raw2) : [];
          const arr2 = Array.isArray(parsed2) ? parsed2 : [];
          setRecentViewsFallback(arr2);
        } catch {
          setRecentViewsFallback([]);
        }
      } catch (e) {
        setError(e?.message || "마이페이지 데이터를 불러오지 못했어요.");
      } finally {
        setLoading(false);
      }
    };

    run();
  }, []);

  const hasApiSessions = recommendationSessions.length > 0;
  const hasApiViews = viewedHistory.length > 0;

  if (loading) {
    return (
      <div className="mypage">
        <div className="mypage-shell">
          <div className="mypage-card">로딩 중...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mypage">
        <div className="mypage-shell">
          <div className="mypage-card">
            <p style={{ color: "#fca5a5", fontWeight: 800 }}>{error}</p>
            <button
              className="mypage-primary-btn"
              onClick={() => navigate("/login")}
            >
              로그인으로
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mypage">
      <div className="mypage-shell">
        {/* 상단 인사 영역 */}
        <header className="mypage-header">
          <h1 className="mypage-title">{displayName}님을 위한 정책 공간</h1>
          <p className="mypage-subtitle">
            최근 추천(결과 페이지)과 검증/열람 기록(Final 페이지)을 한눈에 모아두었어요.
          </p>
        </header>

        {/* 상단 2열 카드: 프로필 + 최근 추천 */}
        <section className="mypage-top-grid">
          {/* 프로필 */}
          <div className="mypage-card profile-card-compact">
            <div className="mypage-card-head">
              <h2>내 프로필</h2>
            </div>

            <div className="profile-compact">
              <div className="profile-avatar" aria-hidden>
                {String(displayName).slice(0, 1)}
              </div>

              <div className="profile-compact-main">
                <div className="profile-name-row">
                  <div className="profile-name">{displayName}</div>
                  <div className="profile-email">{fmtMaybe(profile?.email)}</div>
                </div>

                <div className="profile-chips">
                  <span className="profile-chip">
                    나이: {profile?.age ? `${profile.age}세` : "-"}
                  </span>
                  <span className="profile-chip">
                    거주: {profile?.region ? profile.region : "미설정"}
                  </span>
                  <span className="profile-chip">
                    학생 여부:{" "}
                    {profile?.is_student === true
                      ? "예"
                      : profile?.is_student === false
                      ? "아니오"
                      : "-"}
                  </span>
                  <span className="profile-chip">전공: {fmtMaybe(profile?.major)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* ✅ 오른쪽 위: 최근 추천 받은 정책 및 장학금 */}
          <div className="mypage-card recent-card">
            <div className="mypage-card-head">
              <h2>최근 추천 받은 정책 및 장학금</h2>
              <button
                type="button"
                className="small-link-btn"
                onClick={() => navigate("/result")}
              >
                결과 보기 →
              </button>
            </div>

            {hasApiSessions ? (
              <div className="recent-scroll">
                {recommendationSessions.map((sess, idx) => {
                  const createdAt = sess?.created_at || sess?.createdAt || "";
                  const items = Array.isArray(sess?.items) ? sess.items : [];

                  // ✅ 장학금 "전부"
                  const scholarships = getScholarshipsFromSession(sess);
                  const schCount = scholarships.length;

                  return (
                    <details
                      key={`sess-${createdAt || "t"}-${idx}`}
                      className="recent-details"
                      open={idx === 0}
                    >
                      <summary className="recent-summary">
                        <div className="recent-summary-col">
                          <div className="recent-summary-time">
                            {fmtTime(createdAt)
                              ? `🕒 ${fmtTime(createdAt)}`
                              : "🕒 추천 기록"}
                          </div>
                          <div className="recent-summary-sub">
                            🎓 장학금 {schCount}개{" "}
                            {items.length ? `· 정책 ${items.length}개` : ""}
                          </div>
                        </div>
                      </summary>

                      <div className="recent-details-body">
                        {/* ✅ 장학금 리스트 */}
                        {schCount > 0 ? (
                          <ul className="recent-list" style={{ margin: 0 }}>
                            {scholarships.map((s, sIdx) => (
                              <li
                                key={`sch-${s?.id ?? sIdx}-${createdAt || "t"}`}
                                className="recent-item"
                              >
                                <div className="recent-main">
                                  <p className="recent-title">
                                    🎓 {s?.name || "장학금"}
                                  </p>
                                  <p className="recent-meta">
                                    {s?.category ? `유형: ${s.category}` : "-"}
                                    {s?.user_fit ? ` · 적합도: ${s.user_fit}` : ""}
                                  </p>
                                </div>
                                <span className="recent-status status-recommend">추천</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="empty-block">추천 장학금이 없습니다.</div>
                        )}

                        {/* 정책 리스트 */}
                        {items.length > 0 ? (
                          <ul className="recent-list" style={{ margin: 0 }}>
                            {items.map((p, pIdx) => (
                              <li
                                key={`${p.policy_id ?? pIdx}-${createdAt || "t"}`}
                                className="recent-item"
                              >
                                <div className="recent-main">
                                  <p className="recent-title">
                                    {p.title || "(정책명 없음)"}
                                  </p>
                                  <p className="recent-meta">
                                    <span className="recent-region">
                                      📍 {p.region || "-"}
                                    </span>
                                    <span>·</span>
                                    <span className="recent-category">
                                      {p.category_l || "-"}
                                      {p.category_m ? ` / ${p.category_m}` : ""}
                                    </span>
                                  </p>
                                </div>

                                <span
                                  className={
                                    "recent-status " +
                                    statusClass(p.badge_status || "RECOMMEND")
                                  }
                                  title={p.badge_status || "추천"}
                                >
                                  {p.badge_status || "추천"}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="empty-block">이 추천 기록에 정책이 없습니다.</div>
                        )}
                      </div>
                    </details>
                  );
                })}
              </div>
            ) : recentResultBatchesFallback.length > 0 ? (
              <div className="recent-scroll">
                {recentResultBatchesFallback.map((batch, bIdx) => {
                  const policies = Array.isArray(batch?.policies) ? batch.policies : [];
                  const scholarships = getScholarshipsFromBatch(batch);
                  const schCount = scholarships.length;
                  const createdAt = batch?.created_at || batch?.createdAt || "";

                  return (
                    <details
                      key={`batch-${createdAt || "t"}-${bIdx}`}
                      className="recent-details"
                      open={bIdx === 0}
                    >
                      <summary className="recent-summary">
                        <div className="recent-summary-col">
                          <div className="recent-summary-time">
                            {fmtTime(createdAt)
                              ? `🕒 ${fmtTime(createdAt)}`
                              : "🕒 추천 기록"}
                          </div>
                          <div className="recent-summary-sub">
                            🎓 장학금 {schCount}개{" "}
                            {policies.length ? `· 정책 ${policies.length}개` : ""}
                          </div>
                        </div>
                      </summary>

                      <div className="recent-details-body">
                        {/* ✅ fallback 장학금 리스트 */}
                        {schCount > 0 ? (
                          <ul className="recent-list" style={{ margin: 0 }}>
                            {scholarships.map((s, sIdx) => (
                              <li
                                key={`batch-sch-${s?.id ?? sIdx}-${createdAt || "t"}`}
                                className="recent-item"
                              >
                                <div className="recent-main">
                                  <p className="recent-title">
                                    🎓 {s?.name || "장학금"}
                                  </p>
                                  <p className="recent-meta">
                                    {s?.category ? `유형: ${s.category}` : "-"}
                                    {s?.user_fit ? ` · 적합도: ${s.user_fit}` : ""}
                                  </p>
                                </div>
                                <span className="recent-status status-recommend">추천</span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="empty-block">추천 장학금이 없습니다.</div>
                        )}

                        {policies.length > 0 ? (
                          <ul className="recent-list" style={{ margin: 0 }}>
                            {policies.map((p, idx2) => (
                              <li
                                key={`${p.id ?? p.policy_id ?? idx2}`}
                                className="recent-item"
                              >
                                <div className="recent-main">
                                  <p className="recent-title">
                                    {p.title || "(정책명 없음)"}
                                  </p>
                                  <p className="recent-meta">
                                    <span className="recent-region">
                                      📍 {p.region || "-"}
                                    </span>
                                    <span>·</span>
                                    <span className="recent-category">
                                      {p.category_l || "-"}
                                      {p.category_m ? ` / ${p.category_m}` : ""}
                                    </span>
                                  </p>
                                </div>

                                <span
                                  className={
                                    "recent-status " +
                                    statusClass(p.badge_status || "RECOMMEND")
                                  }
                                  title={p.badge_status || "추천"}
                                >
                                  {p.badge_status || "추천"}
                                </span>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <div className="empty-block">이 추천 묶음에 정책이 없습니다.</div>
                        )}
                      </div>
                    </details>
                  );
                })}
              </div>
            ) : (
              <div className="empty-block">
                아직 추천받은 기록이 없어요.
                <br />
                Question → Result에서 추천을 먼저 받아보세요.
              </div>
            )}
          </div>
        </section>

        {/* 하단: 최근 열람(검증) + CTA */}
        <section className="mypage-bottom">
          {/* ✅ 왼쪽 아래: 최근에 살펴본 정책 및 장학금 */}
          <div className="mypage-card history-card">
            <div className="mypage-card-head">
              <h2>최근에 살펴본 정책 및 장학금</h2>
              <span className="subtle-count">
                {(hasApiViews ? viewedHistory.length : recentViewsFallback.length) || 0}개
              </span>
            </div>

            {hasApiViews ? (
              <div className="history-scroll">
                <ul className="history-list history-list-rows">
                  {viewedHistory.map((item, idx) => {
                    const scholarship = item?.scholarship || null;

                    return (
                      <li
                        key={`${item.policy_id ?? "p"}-${item.viewed_at ?? "t"}-${idx}`}
                        className="history-row"
                      >
                        <div className="history-row-left">
                          <div className="dot" />
                          <div className="history-texts">
                            <p className="history-title">{item.title || "(정책명 없음)"}</p>

                            <p className="history-meta">
                              📍 {item.region || "-"}
                              {" · "}
                              {item.category_l || "-"}
                              {item.category_m ? ` / ${item.category_m}` : ""}
                              {item.verification_status
                                ? ` · 검증: ${item.verification_status}`
                                : ""}
                            </p>

                            <p className="history-meta" style={{ marginTop: 4 }}>
                              🎓 {scholarship?.name || "장학금 정보 없음"}
                              {scholarship?.category ? ` · 유형: ${scholarship.category}` : ""}
                              {scholarship?.user_fit ? ` · 적합도: ${scholarship.user_fit}` : ""}
                            </p>
                          </div>
                        </div>

                        <button
                          type="button"
                          className="row-link-btn"
                          onClick={() =>
                            navigate(`/final/${item.policy_id}`, {
                              state: { selectedScholarship: scholarship || null },
                            })
                          }
                          title="최종 추천 페이지로 이동"
                        >
                          보기 →
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ) : recentViewsFallback.length > 0 ? (
              <div className="history-scroll">
                <ul className="history-list history-list-rows">
                  {recentViewsFallback.map((x, idx) => (
                    <li
                      key={`${x?.policy_id ?? "p"}-${x?.viewed_at ?? "t"}-${idx}`}
                      className="history-row"
                    >
                      <div className="history-row-left">
                        <div className="dot" />
                        <div className="history-texts">
                          <p className="history-title">
                            {x?.policy_title || `정책 #${x?.policy_id ?? "-"}`}
                          </p>
                          <p className="history-meta">
                            📍 {x?.policy_region || "-"}
                            {" · "}
                            {x?.policy_category || "-"}
                            {x?.verification_status ? ` · 검증: ${x.verification_status}` : ""}
                          </p>
                          <p className="history-meta" style={{ marginTop: 4 }}>
                            🎓 {x?.scholarship?.name || "장학금 정보 없음"}
                            {x?.scholarship?.category ? ` · 유형: ${x.scholarship.category}` : ""}
                            {x?.scholarship?.user_fit ? ` · 적합도: ${x.scholarship.user_fit}` : ""}
                          </p>
                        </div>
                      </div>

                      <button
                        type="button"
                        className="row-link-btn"
                        onClick={() =>
                          navigate(`/final/${x?.policy_id}`, {
                            state: { selectedScholarship: x?.scholarship || null },
                          })
                        }
                        title="검증/열람한 최종 페이지로 이동"
                      >
                        보기 →
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="empty-block">
                아직 Final에서 살펴본(검증한) 기록이 없어요.
                <br />
                Result에서 정책을 선택해 Final로 들어가보면 여기에 쌓여요.
              </div>
            )}
          </div>

          {/* CTA */}
          <div className="mypage-cta-card">
            <h2>다시 정책 추천 받으러 가볼까요?</h2>
            <p>조건이 달라졌다면 다시 선택해서 새로운 추천을 받아보는 것도 좋아요.</p>
            <div className="mypage-cta-actions">
              <button
                type="button"
                className="mypage-primary-btn"
                onClick={() => navigate("/question")}
              >
                조건 다시 선택하러 가기
              </button>
              <button
                type="button"
                className="mypage-secondary-btn"
                onClick={() => navigate("/")}
              >
                처음 화면으로 돌아가기
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

export default MyPage;
