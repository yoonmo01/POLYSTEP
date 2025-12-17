//frontend/my-react-app/src/pages/Homepage.jsx
import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import heroBg from "../assets/HomePage_BackGround.jpg";
import PolicySitesGraph from "../components/PolicySitesGraph";
import "./Homepage.css";

import { clearUser } from "../auth";
import { apiFetch } from "../api";

const HomePage = () => {
  const navigate = useNavigate();
  const [user, setUserState] = useState(null);

  useEffect(() => {
    apiFetch("/me")
      .then((me) => {
        setUserState({
          ...me,
          name: me.name ?? me.full_name ?? me.fullName ?? "사용자",
        });
      })
      .catch(() => setUserState(null));
  }, []);

  const handleLogout = () => {
    clearUser();
    setUserState(null);
    navigate("/");
  };

  return (
    <div
      className="home"
      style={{
        backgroundImage: `linear-gradient(
          to bottom right,
          rgba(5, 10, 35, 0.85),
          rgba(6, 40, 80, 0.85)
        ), url(${heroBg})`,
      }}
    >
      <header className="home-header">
        <div className="home-logo">POLYSTEP</div>

        <nav className="home-nav">
          {user ? (
            <>
              <span className="nav-greet">안녕하세요, {user.name}님</span>
              <button type="button" className="nav-link nav-btn" onClick={handleLogout}>
                로그아웃
              </button>
              <Link to="/mypage" className="nav-link">
                마이페이지
              </Link>
            </>
          ) : (
            <>
              <Link to="/mypage" className="nav-link">
                마이페이지
              </Link>
              <Link to="/login" className="nav-link">
                로그인
              </Link>
              <Link to="/signup" className="nav-link">
                회원가입
              </Link>
            </>
          )}
        </nav>
      </header>

      <main className="home-main">
        <section className="home-hero">
          <p className="home-tag">나에게 딱 맞는 정책, 한 번에 찾기</p>
          <h1 className="home-title">
            복잡한 공고문 대신,
            <br />
            <span>사용자 친화적 정책 가이드</span>
          </h1>
          <p className="home-subtitle">
            폴리스탭은 청년 정책·장학금·지원사업 정보를 AI로 분석해서,
            <br />
            <strong>지금 나에게 필요한 혜택</strong>부터 보여주는 서비스입니다.
          </p>

          <div className="home-actions">
            <Link to="/question" className="btn btn-primary">
              나에게 맞는 정책 찾기
            </Link>
            {/* <Link to="/about" className="btn btn-ghost">
              서비스 소개 보기
            </Link> */}
          </div>

          <div className="home-badges">
            <div className="badge">
              🎯 맞춤 추천
              <span>연령 · 소득 · 거주지 기반 필터링</span>
            </div>
            <div className="badge">
              📊 한눈에 비교
              <span>지원 금액 · 기간 · 경쟁도 요약</span>
            </div>
            <div className="badge">
              🧭 쉽게 이동
              <span>공식 신청 페이지 바로가기</span>
            </div>
          </div>
        </section>

        <section className="home-info">
          <div className="info-card">
            <h3>정책 찾기, 왜 이렇게 어려울까?</h3>
            <p>
              수많은 사이트와 공고문을 돌아다니며 조건을 하나씩 확인하는 대신,
              폴리스탭에서 한 번만 조건을 입력하면 핵심 정보만 정리해서 보여줍니다.
            </p>
          </div>
          <div className="info-grid">
            <div className="info-item">
              <h4>공식 데이터 기반</h4>
              <p>정부·지자체의 공신력 있는 데이터를 바탕으로 정보를 제공합니다.</p>
            </div>
            <div className="info-item">
              <h4>카드형 UI</h4>
              <p>딱딱한 문서 대신, 카드 뉴스처럼 직관적인 UI로 구성했습니다.</p>
            </div>
            <div className="info-item">
              <h4>AI 요약</h4>
              <p>긴 공고문을 읽지 않아도, 핵심만 빠르게 파악할 수 있습니다.</p>
            </div>
          </div>
        </section>

        <section className="home-graph">
          <div className="home-graph-header">
            <h2>POLYSTEP 통합 그래프</h2>
            <p>
              온통청년·한국장학재단 등 다양한 청년 정책/장학 사이트 정보를 POLYSTEP에서
              한 번에 연결해 보여줍니다.
            </p>
          </div>

          <div className="home-graph-card">
            <div className="home-graph-canvas">
              <PolicySitesGraph />
            </div>
          </div>
        </section>
      </main>

      <footer className="home-footer">
        <span>© 2025 POLYSTEP · Open Source Project</span>
      </footer>
    </div>
  );
};

export default HomePage;
