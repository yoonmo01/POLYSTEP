//frontend/my-react-app/src/pages/MyPage.jsx
import "./MyPage.css";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../api";

const fmtMaybe = (v) => (v == null || v === "" ? "-" : String(v));

function MyPage() {
  const navigate = useNavigate();

  const [profile, setProfile] = useState(null);
  const [recentRecommendations, setRecentRecommendations] = useState([]);
  const [viewedHistory, setViewedHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const displayName = useMemo(
    () => profile?.name || profile?.full_name || "사용자",
    [profile]
  );

  useEffect(() => {
    const run = async () => {
      try {
        setLoading(true);
        setError("");

        const [me, rec, views] = await Promise.all([
          apiFetch("/me"),
          apiFetch("/me/recommendations?limit=1"),
          apiFetch("/me/views?limit=10"),
        ]);

        setProfile(me);
        setRecentRecommendations(Array.isArray(rec?.items) ? rec.items : []);
        setViewedHistory(Array.isArray(views?.items) ? views.items : []);
      } catch (e) {
        setError(e?.message || "마이페이지 데이터를 불러오지 못했어요.");
      } finally {
        setLoading(false);
      }
    };
    run();
  }, []);

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
            <button className="mypage-primary-btn" onClick={() => navigate("/login")}>
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
            최근에 본 정책과 추천 결과를 한눈에 모아두었어요.
            <br className="only-mobile" />
            필요할 때 언제든지 다시 확인하고, 조건을 바꿔 새로운 추천도 받아보세요.
          </p>
        </header>

        {/* 상단 2열 카드: 프로필(컴팩트) + 최근 추천 */}
        <section className="mypage-top-grid">
          {/* ✅ 프로필: 큰 박스 → 컴팩트 요약 카드 */}
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
                </div>
              </div>
            </div>
          </div>

          {/* 최근 추천 카드 */}
          <div className="mypage-card recent-card">
            <div className="mypage-card-head">
              <h2>최근 추천 받은 정책</h2>
              <button
                type="button"
                className="small-link-btn"
                onClick={() => navigate("/result")}
              >
                결과 보기 →
              </button>
            </div>

            {recentRecommendations.length > 0 ? (
              <ul className="recent-list">
                {recentRecommendations.map((item) => (
                  <li
                    key={item.id ?? `${item.policy_id}-${item.title}`}
                    className="recent-item"
                  >
                    <div className="recent-main">
                      {/* 제목 */}
                      <p className="recent-title">{item.title}</p>

                      {/* 메타 정보: 지역 + 분야 */}
                      <p className="recent-meta">
                        <span className="recent-region">
                          📍 {item.region || "-"}
                        </span>
                        <span>·</span>
                        <span className="recent-category">
                          {item.category_l || "-"}
                          {item.category_m ? ` / ${item.category_m}` : ""}
                        </span>
                      </p>
                    </div>

                    {/* 상태 뱃지 */}
                    <span
                      className={
                        "recent-status" +
                        (item.badge_status
                          ? ` status-${String(item.badge_status).toLowerCase()}`
                          : " status-recommend")
                      }
                    >
                      {item.badge_status || "추천"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-block">
                아직 추천 받은 정책이 없어요.
                <br />
                홈에서 추천을 처음 받아보세요.
              </div>
            )}
          </div>
        </section>

        {/* 하단: 히스토리 + CTA */}
        <section className="mypage-bottom">
          <div className="mypage-card history-card">
            <div className="mypage-card-head">
              <h2>최근에 살펴본 정책</h2>
              <span className="subtle-count">{viewedHistory.length}개</span>
            </div>

            {viewedHistory.length > 0 ? (
              <ul className="history-list history-list-rows">
                {viewedHistory.map((item) => (
                  <li key={item.id ?? `${item.policy_id}-${item.title}`} className="history-row">
                    <div className="history-row-left">
                      <div className="dot" />
                      <div className="history-texts">
                        <p className="history-title">{item.title}</p>
                        <p className="history-meta">{item.category || "-"}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      className="row-link-btn"
                      onClick={() => navigate(`/final/${item.policy_id || item.id}`)}
                      title="최종 추천 페이지로 이동"
                    >
                      보기 →
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="empty-block">
                최근에 본 정책이 아직 없어요.
                <br />
                추천 결과 페이지에서 관심 정책을 살펴보면 이곳에 쌓여요.
              </div>
            )}
          </div>

          <div className="mypage-cta-card">
            <h2>다시 정책 추천 받으러 가볼까요?</h2>
            <p>
              지금 상황이 달라졌다면, 연소득이나 취업 상태, 관심 분야를 업데이트하고
              <br className="only-mobile" />
              새로운 추천을 받아보는 것도 좋아요.
            </p>
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
