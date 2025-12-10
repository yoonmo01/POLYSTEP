import { useNavigate } from "react-router-dom";
import { useState } from "react";

function ResultPage() {
  const navigate = useNavigate();
  // 나중에 선택한 정책의 URL을 상태로 관리하면 됨
  const [selectedPolicyUrl] = useState(""); // 아직은 빈 값

  return (
    <section className="page result-page">
      <h2>추천 정책 결과</h2>
      <p className="subtitle">
        입력한 정보를 바탕으로 추천된 정책 목록입니다.
      </p>

      {/* 🔹 왼쪽(정책 카드) + 오른쪽(아이프레임) 레이아웃 */}
      <div className="result-layout">
        {/* 왼쪽: 결과 카드 리스트 */}
        <div className="result-left">
          <div className="card-list">
            <div className="card">
              <h3>청년 주거 지원 정책</h3>
              <p>전세, 월세 부담을 줄이기 위한 청년 대상 주거 지원.</p>
            </div>
            <div className="card">
              <h3>청년 취업 지원 패키지</h3>
              <p>취업 컨설팅, 직무 교육, 인턴 연계 프로그램.</p>
            </div>
            <div className="card">
              <h3>학자금 상환 지원</h3>
              <p>학자금 대출 상환 부담을 줄이기 위한 지원 제도.</p>
            </div>
          </div>
        </div>

        {/* 오른쪽: 정책 홈페이지 아이프레임 영역 */}
        <div className="result-right">
          <div className="iframe-wrapper">
            {selectedPolicyUrl ? (
              <iframe
                src={selectedPolicyUrl}
                title="policy-site"
                loading="lazy"
              />
            ) : (
              <div className="iframe-placeholder">
                정책을 선택하면<br />
                해당 정책의 홈페이지가<br />
                이 영역에 표시됩니다.
              </div>
            )}
          </div>
        </div>
      </div>

      <button className="primary-btn" onClick={() => navigate("/final")}>
        최종 결과 화면으로
      </button>
    </section>
  );
}

export default ResultPage;