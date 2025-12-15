//frontend/my-react-app/src/pages/MyPage.jsx
import "./MyPage.css";
import { useNavigate } from "react-router-dom";

function MyPage() {
  const navigate = useNavigate();

  // TODO: 나중에 실제 프로필/추천 데이터 연동
  const profile = {
    name: "청년 사용자",
    email: "user@example.com",
    age: 24,
    region: "강원도 춘천시",
  };

  const recentRecommendations = [
    {
      id: 1,
      title: "청년 주거 지원 바우처",
      category: "생활·주거",
      status: "관심 정책",
      updatedAt: "2025-12-10",
    },
    {
      id: 2,
      title: "청년 취업 성공 패키지",
      category: "일자리·취업",
      status: "추천 완료",
      updatedAt: "2025-12-09",
    },
    {
      id: 3,
      title: "대학생 등록금 지원 장학금",
      category: "교육·훈련",
      status: "조회 완료",
      updatedAt: "2025-12-08",
    },
  ];

  const viewedHistory = [
    {
      id: 1,
      title: "청년 전세자금 대출",
      category: "생활·주거",
    },
    {
      id: 2,
      title: "청년 지역 정착 지원금",
      category: "지역 정착",
    },
    {
      id: 3,
      title: "청년 창업 지원 패키지",
      category: "창업·소상공인",
    },
  ];

  return (
    <div className="mypage">
      <div className="mypage-shell">
        {/* 상단 인사 영역 */}
        <header className="mypage-header">
          <h1 className="mypage-title">
            {profile.name}님을 위한 정책 공간
          </h1>
          <p className="mypage-subtitle">
            최근에 본 정책과 추천 결과를 한눈에 모아두었어요.
            <br className="only-mobile" />
            필요할 때 언제든지 다시 확인하고, 조건을 바꿔 새로운 추천도 받아보세요.
          </p>
        </header>

        {/* 상단 2열 카드: 프로필 + 최근 추천 */}
        <section className="mypage-top-grid">
          {/* 프로필 요약 카드 */}
          <div className="mypage-card profile-card">
            <div className="mypage-card-head">
              <h2>내 프로필</h2>
              <button
                type="button"
                className="profile-edit-btn"
                onClick={() => navigate("/profile")}
              >
                프로필 수정하기
              </button>
            </div>

            <div className="profile-info-grid">
              <div className="profile-info-item">
                <span className="label">이름</span>
                <span className="value">{profile.name}</span>
              </div>
              <div className="profile-info-item">
                <span className="label">이메일</span>
                <span className="value">{profile.email}</span>
              </div>
              <div className="profile-info-item">
                <span className="label">나이</span>
                <span className="value">
                  {profile.age ? `${profile.age}세` : "-"}
                </span>
              </div>
              <div className="profile-info-item">
                <span className="label">거주 지역</span>
                <span className="value">
                  {profile.region || "설정되지 않음"}
                </span>
              </div>
            </div>

            <p className="profile-hint">
              프로필을 업데이트하면 추천 정책의 정확도도 함께 높아져요.
            </p>
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
                결과 다시 보러가기 →
              </button>
            </div>

            {recentRecommendations.length > 0 ? (
              <ul className="recent-list">
                {recentRecommendations.map((item) => (
                  <li key={item.id} className="recent-item">
                    <div className="recent-main">
                      <p className="recent-title">{item.title}</p>
                      <p className="recent-meta">
                        <span>{item.category}</span>
                        <span>·</span>
                        <span>{item.updatedAt}</span>
                      </p>
                    </div>
                    <span className="recent-status">{item.status}</span>
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
            </div>

            {viewedHistory.length > 0 ? (
              <ul className="history-list">
                {viewedHistory.map((item) => (
                  <li key={item.id} className="history-item">
                    <div className="dot" />
                    <div className="history-texts">
                      <p className="history-title">{item.title}</p>
                      <p className="history-meta">{item.category}</p>
                    </div>
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
              지금 상황이 달라졌다면, 연소득이나 취업 상태, 관심 분야를
              업데이트하고
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
