import { Routes, Route, Link, useLocation } from "react-router-dom";

import "./App.css";
import HomePage from "./pages/Homepage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import QuestionPage from "./pages/QuestionPage";
import ResultPage from "./pages/ResultPage";
import FinalPage from "./pages/FinalPage";
import MyPage from "./pages/MyPage";

function App() {
  const location = useLocation();
  const isHome = location.pathname === "/";

  return (
    <>
      {/* 홈이 아닐 때만 상단 네비게이션 표시 */}
      {!isHome && (
        <header className="app-header">
          <nav className="app-nav">
            <Link to="/" className="app-logo">
              POLYSTEP
            </Link>

            <div className="app-nav-right">
              <Link to="/login" className="app-nav-btn">
                로그인
              </Link>
              <Link to="/signup" className="app-nav-btn">
                회원가입
              </Link>
              
              <Link to="/mypage" className="app-nav-btn app-nav-btn-outline">
                마이페이지
              </Link>
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
