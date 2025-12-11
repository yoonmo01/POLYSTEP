import { Routes, Route, Link, useLocation } from "react-router-dom";

import "./App.css";
import HomePage from "./pages/Homepage";
import ProfilePage from "./pages/ProFilePage";
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
              <Link to="/profile" className="app-nav-btn">
                프로필 설정
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
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/question" element={<QuestionPage />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/final" element={<FinalPage />} />
        <Route path="/mypage" element={<MyPage />} />
      </Routes>
    </>
  );
}

export default App;
