import { useNavigate } from "react-router-dom";
import { useState } from "react";

function QuestionPage() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    income: "",
    policyField: "제한없음",
    employmentStatus: "제한없음",
    specialField: "제한없음",
  });

  // 숫자 입력(연소득)
  const handleIncomeChange = (e) => {
    const value = e.target.value;
    // 숫자만 허용 (빈 값은 허용)
    if (value === "" || /^[0-9]+$/.test(value)) {
      setForm((prev) => ({ ...prev, income: value }));
    }
  };

  // 버튼 선택 공통 핸들러
  const handleSelect = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // TODO: form 데이터를 전역상태/DB로 넘기는 로직 추가
    console.log("선택한 값:", form);
    navigate("/result"); // 8페이지로 이동
  };

  // 👉 아래 배열들은 화면 설계서 7페이지 컨셉에 맞춰 임시로 넣은 것이라,
  // 실제 DB 스키마에 맞게 나중에 값만 교체해주면 됨.
  const policyOptions = [
    "취업",
    "주거",
    "생활비",
    "교육",
    "건강·복지",
    "기타",
  ];

  const employmentOptions = [
    "대학생",
    "취업준비생",
    "재직자",
    "프리랜서",
    "무직",
  ];

  const specialOptions = [
    "창업·자영업",
    "장애",
    "저소득",
    "다자녀",
    "농어촌",
    "기타",
  ];

  return (
    <section className="page question-page">
      <h2>맞춤 정책 추천을 위한 정보 입력</h2>
      <p className="subtitle">
        연소득과 관심 분야를 선택하면, POLYSTEP가 맞춤 정책을 찾아드릴게요.
      </p>

      <form className="question-form" onSubmit={handleSubmit}>
        {/* 1. 연소득 섹션 */}
        <div className="question-section">
          <h3>1. 연소득</h3>
          <p className="section-desc">
            현재 본인의 연간 소득을 입력해주세요. (단위: 만 원)
          </p>
          <div className="inline-input">
            <input
              type="text"
              placeholder="예: 2400"
              value={form.income}
              onChange={handleIncomeChange}
            />
            <span className="unit-label">만 원</span>
          </div>
        </div>

        {/* 2. 정책 분야 섹션 */}
        <div className="question-section">
          <h3>2. 관심 정책 분야</h3>
          <p className="section-desc">
            관심 있는 정책 분야를 선택해주세요. 모든 분야를 보고 싶다면
            <strong> 제한없음</strong>을 선택하세요.
          </p>
          <div className="option-buttons">
            {policyOptions.map((opt) => (
              <button
                type="button"
                key={opt}
                className={
                  "option-button" +
                  (form.policyField === opt ? " selected" : "")
                }
                onClick={() => handleSelect("policyField", opt)}
              >
                {opt}
              </button>
            ))}
            <button
              type="button"
              className={
                "option-button outline" +
                (form.policyField === "제한없음" ? " selected" : "")
              }
              onClick={() => handleSelect("policyField", "제한없음")}
            >
              제한없음
            </button>
          </div>
        </div>

        {/* 3. 취업 상태 섹션 */}
        <div className="question-section">
          <h3>3. 현재 취업 상태</h3>
          <p className="section-desc">
            현재 본인의 상황에 가장 가까운 항목을 선택해주세요.
          </p>
          <div className="option-buttons">
            {employmentOptions.map((opt) => (
              <button
                type="button"
                key={opt}
                className={
                  "option-button" +
                  (form.employmentStatus === opt ? " selected" : "")
                }
                onClick={() => handleSelect("employmentStatus", opt)}
              >
                {opt}
              </button>
            ))}
            <button
              type="button"
              className={
                "option-button outline" +
                (form.employmentStatus === "제한없음" ? " selected" : "")
              }
              onClick={() => handleSelect("employmentStatus", "제한없음")}
            >
              제한없음
            </button>
          </div>
        </div>

        {/* 4. 특화 분야 섹션 */}
        <div className="question-section">
          <h3>4. 특화 분야</h3>
          <p className="section-desc">
            본인이 해당되는 특화 카테고리가 있다면 선택해주세요. 없으면
            <strong> 제한없음</strong>을 선택하면 됩니다.
          </p>
          <div className="option-buttons">
            {specialOptions.map((opt) => (
              <button
                type="button"
                key={opt}
                className={
                  "option-button" +
                  (form.specialField === opt ? " selected" : "")
                }
                onClick={() => handleSelect("specialField", opt)}
              >
                {opt}
              </button>
            ))}
            <button
              type="button"
              className={
                "option-button outline" +
                (form.specialField === "제한없음" ? " selected" : "")
              }
              onClick={() => handleSelect("specialField", "제한없음")}
            >
              제한없음
            </button>
          </div>
        </div>

        {/* 제출 버튼 */}
        <div className="question-submit">
          <button type="submit" className="primary-btn">
            정책 추천 생성하기
          </button>
        </div>
      </form>
    </section>
  );
}

export default QuestionPage;