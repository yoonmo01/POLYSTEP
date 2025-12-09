function MyPage() {
  return (
    <section className="page mypage">
      <h2>마이페이지</h2>
      <p>저장한 정책, 관심 정책, 최근 본 정책 등을 관리하는 화면입니다.</p>

      <div className="card-grid">
        <div className="card">
          <h3>저장한 정책</h3>
          <p>내가 찜한 정책 목록을 확인할 수 있어요.</p>
        </div>
        <div className="card">
          <h3>알림 설정</h3>
          <p>새로운 정책 업데이트 알림을 받을 수 있어요.</p>
        </div>
        <div className="card">
          <h3>개인 정보</h3>
          <p>연령, 지역, 관심 분야 등을 수정할 수 있어요.</p>
        </div>
      </div>
    </section>
  );
}

export default MyPage;
