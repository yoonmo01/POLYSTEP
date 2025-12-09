import { Routes, Route, Link } from "react-router-dom";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage.jsx";
import MainPage from "./pages/MainPage";
import QuestionPage from "./pages/QuestionPage";
import ResultPage from "./pages/ResultPage";
import FinalPage from "./pages/FinalPage.jsx";
import MyPage from "./pages/MyPage";

function App() {
  return (
    <div className="app">
      {/* 상단 공통 헤더 (필요 없으면 삭제해도 됨) */}
      <header className="app-header">
        <Link to="/" className="logo">
          POLYSTEP
        </Link>
        <nav className="nav">
          <Link to="/main">홈페이지</Link>
          <Link to="/mypage">마이페이지</Link>
        </nav>
      </header>

      <main className="app-main">
        <Routes>
          {/* 3페이지: Home */}
          <Route path="/" element={<HomePage />} />

          {/* 4페이지: Login */}
          <Route path="/login" element={<LoginPage />} />

          {/* 회원가입 */}
          <Route path="/signup" element={<SignupPage />} />

          {/* 5+6페이지: Main (위/아래 한 화면, 스크롤) */}
          <Route path="/main" element={<MainPage />} />

          {/* 7페이지: 입력 폼 */}
          <Route path="/question" element={<QuestionPage />} />

          {/* 8페이지: 추천 결과 리스트 */}
          <Route path="/result" element={<ResultPage />} />

          {/* 9페이지: 최종 화면 */}
          <Route path="/final" element={<FinalPage />} />

          {/* 10페이지: 마이페이지 */}
          <Route path="/mypage" element={<MyPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;