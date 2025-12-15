import { Routes, Route, Link, useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

import "./App.css";
import HomePage from "./pages/Homepage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import QuestionPage from "./pages/QuestionPage";
import ResultPage from "./pages/ResultPage";
import FinalPage from "./pages/FinalPage";
import MyPage from "./pages/MyPage";

import { getUser, clearUser } from "./auth";

function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const isHome = location.pathname === "/";

  const [user, setUserState] = useState(getUser());

  // 다른 탭에서 로그아웃/로그인해도 동기화
  useEffect(() => {
    const onStorage = () => setUserState(getUser());
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  // 페이지 이동할 때도 localStorage 기준으로 한 번 갱신
  useEffect(() => {
    setUserState(getUser());
  }, [location.pathname]);

  const handleLogout = () => {
    clearUser();
    setUserState(null);
    navigate("/");
  };

  return (
    <>
      {!isHome && (
        <header className="app-header">
          <nav className="app-nav">
            <Link to="/" className="app-logo">
              POLYSTEP
            </Link>

            <div className="app-nav-right">
              {user ? (
                <>
                  <span className="app-nav-greet">안녕하세요, {user.name}님</span>
                  <button type="button" className="app-nav-btn" onClick={handleLogout}>
                    로그아웃
                  </button>
                  <Link to="/mypage" className="app-nav-btn app-nav-btn-outline">
                    마이페이지
                  </Link>
                </>
              ) : (
                <>
                  <Link to="/login" className="app-nav-btn">
                    로그인
                  </Link>
                  <Link to="/signup" className="app-nav-btn">
                    회원가입
                  </Link>
                  <Link to="/mypage" className="app-nav-btn app-nav-btn-outline">
                    마이페이지
                  </Link>
                </>
              )}
            </div>
          </nav>
        </header>
      )}

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/question" element={<QuestionPage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/final" element={<FinalPage />} />
        <Route path="/mypage" element={<MyPage />} />
      </Routes>
    </>
  );
}

export default App;
