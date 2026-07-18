# POLYSTEP — Production Readiness Roadmap

## 현재 상태 (실제 코드 확인 기준)

| 항목 | 상태 |
|---|---|
| 인증 | JWT 있음 (`security.py`, pbkdf2_sha256 해싱 — bcrypt 72바이트 버그 회피까지 고려된 좋은 선택) |
| CORS | 명시적 origin 화이트리스트 — 양호 |
| DB 커넥션 | `pool_pre_ping=True`만 설정, `pool_size`/`max_overflow` 미설정(기본값 의존) |
| 검증 작업(Deep Track) | `BackgroundTasks`로 `run_verification_job_sync` 실행 → **같은 워커 프로세스 안에서 동기 실행**. browser-use는 페이지 로딩만 몇 초씩 걸리는 무거운 작업이라, 동시 검증 요청이 몰리면 워커 스레드풀이 막힘 |
| Rate Limit | 없음 |
| 로깅 | `print()`문 존재 (`main.py`), 구조화 로깅 없음 |
| Refresh Token | 없음 (access token만, 만료되면 재로그인) |

---

## Phase A — 보안/트래픽 하드닝

파일 대상: `backend/app/main.py`, `backend/app/db.py`, `backend/app/security.py`,
`backend/app/routers/policies.py`, `backend/app/services/policy_verification_service.py`

1. **Rate Limiting** (`slowapi` 도입)
   - Fast Track 검색(`/policies` 검색 엔드포인트): 사용자별/IP별 분당 제한
   - Deep Track 검증 요청(`POST .../verify`): 이건 browser-use라 훨씬 비싸니 더 빡빡한 제한 + 이미 PENDING인 정책은 중복 요청 차단
2. **DB 커넥션 풀 명시적 설정**
   ```python
   engine = create_engine(
       str(settings.database_url),
       future=True,
       pool_pre_ping=True,
       pool_size=10,
       max_overflow=20,
       pool_timeout=30,
   )
   ```
   숫자는 예상 동시접속 기준으로 잡고, 왜 이 값인지 문서화.
3. **검증 작업을 진짜 백그라운드 워커로 분리**
   - `run_verification_job_sync`를 FastAPI `BackgroundTasks`에서 Celery(+Redis broker) 또는 RQ 태스크로 이관
   - 이유: browser-use 작업이 API 서버 프로세스와 분리돼야 검증 요청 폭주가 검색 API 응답속도에 영향 안 줌
   - 큐 길이/처리 시간 메트릭 노출 (Phase B 모니터링과 연결)
4. **Refresh Token 추가**
   - access token(짧은 만료, 15분) + refresh token(길게, 회전형) 구조로 확장
   - `security.py`의 `create_access_token` 옆에 `create_refresh_token` 추가, `/auth/refresh` 엔드포인트 신설
5. **로깅 정리**
   - `print()` 전부 `logging`/`loguru`로 교체, 요청 ID 기반 구조화 로깅
   - Gemini 호출 실패, 검증 실패(`FAILED`), rate limit 차단 이벤트는 반드시 로그에 남기기
6. **Fast Track 응답 캐싱**
   - 이미 `ScholarshipLLMCache` 패턴이 있으니 동일 철학으로 `PolicyEligibilityCache` 신설
   - 같은 (policy_id, 사용자 조건 해시) 조합은 짧은 TTL(예: 1시간)로 캐시 → Gemini 호출 수 감소

**체크포인트**: 부하테스트(locust 등)로 rate limit 전/후 응답시간과 Gemini 호출 횟수 비교 수치 확보.

---

## Phase B — 배포 준비

1. **인프라**
   - 지금 프론트가 `13.125.63.208:5173` 같은 raw IP를 직접 참조 중 — 실제 배포 시 도메인 구매 + HTTPS(Let's Encrypt or Cloudflare) 필수
   - 프론트/백엔드 앞단에 Cloudflare나 Nginx 리버스 프록시 → 여기서 1차 rate limit/DDoS 방어까지 겸함
2. **시크릿 관리**
   - `.env`는 로컬 개발용으로 유지, 배포 환경은 AWS Secrets Manager / GitHub Actions Secrets로 분리
   - `SECRET_KEY`(JWT), `GOOGLE_API_KEY`, `DATABASE_URL` 로테이션 정책 문서화
3. **CI/CD**
   - GitHub Actions: PR마다 테스트 실행 → main 브랜치 머지 시 자동 배포
   - 마이그레이션 도구 도입 검토 (`Base.metadata.create_all`은 스키마 변경 추적이 안 됨 → Alembic 도입 권장)
4. **모니터링**
   - 헬스체크 엔드포인트(`/health`) 추가
   - 에러 트래킹(Sentry 무료 티어) — Gemini 호출 실패, 검증 실패율 알람
   - 업타임 모니터링(UptimeRobot 등, 무료)

---

## Phase C — 사업성/컴플라이언스 체크리스트

이 항목들은 법률 자문이 아니라 "실제로 서비스를 운영하려면 확인해야 할 것들"에 대한 일반적 체크리스트임. 확정적 법률 판단이 필요하면 전문가 확인 필요.

1. **공공데이터 API 이용 약관 확인**
   - 온통청년 API, 강원도 API 등에서 데이터를 가져와 가공·재제공하는 구조 → 각 API의 이용약관(공공누리 라이선스 유형, 상업적 이용 가능 여부, 호출량 제한, 출처 표기 의무) 확인 필요
2. **개인정보처리방침**
   - 회원가입 시 email/password/age/region/academic_status 등 수집 → 실사용자 대상 배포 시 개인정보처리방침 게시, 수집 동의 절차, 보관/파기 정책 필요 (개인정보보호법 대상)
3. **정보 정확성에 대한 면책 문구**
   - "이 정책은 AI가 요약한 것이며 정확한 신청 조건은 반드시 원문/기관에서 재확인하십시오" 같은 문구 — Deep Track 검증이 실패했거나 오래된 캐시일 때 특히 중요
4. **비용 모델**
   - Gemini API는 사용량 기반 과금 → 월 예상 트래픽 기준 단위 경제성(request당 비용) 계산해두면 "실제 서비스로 운영 가능한 프로젝트"라는 근거가 됨
   - 무료 티어로 운영할 경우의 트래픽 상한선도 계산해두기

---

## 정리: 추가/변경되는 것

| 유형 | 대상 |
|---|---|
| **신규 파일** | `rate_limiter.py`(slowapi 설정), Celery worker 설정, `alembic/` 마이그레이션, `/health` 라우터 |
| **수정 파일** | `main.py`(로깅/헬스체크), `db.py`(풀 설정), `security.py`(refresh token), `policies.py`(rate limit 데코레이터), `policy_verification_service.py`(Celery 태스크로 전환) |
| **손 안 대는 것** | 기존 인증 로직 자체, CORS 화이트리스트 방식, HWP/PDF 파싱 파이프라인 |
| **신규 인프라** | Redis(캐시+Celery broker), Sentry, 도메인+HTTPS, GitHub Actions |
