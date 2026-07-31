# SalesCoach 배포 가이드

## Streamlit Community Cloud (데모)

1. New app → Repository: kieokkim/sales-coach, Branch: main,
   Main file path: streamlit_app.py
2. Advanced settings → Python version: 3.13
   (pyproject.toml 삭제로 requires-python 선언이 사라졌으므로 여기서 직접 지정 필수)
3. Secrets — 반드시 최상위 언네임드 키로 넣을 것 (섹션[section] 밑에 넣으면
   os.environ에 노출 안 됨):

DEMO_MODE = "true" OPENAI_API_KEY = "sk-..."
   - OPENAI_API_KEY는 데모 전용으로 새로 발급한 키 사용 (실 운영 키 재사용 금지)
4. OpenAI 대시보드(platform.openai.com → Billing → Limits)에서 이 키에
   하드 스펜딩 캡 설정 — 유일한 확실 비용 방어선
5. Deploy → 배포 완료 후 URL 확인

## 라이브 검증 체크리스트 (배포 후 사람이 직접)
- [ ] 최초 접속 시 자동 시딩 동작 (빈 DB 아님)
- [ ] 데모 배너 노출
- [ ] 비밀번호 게이트가 DEMO_MODE에서 자동 우회
- [ ] 채팅 페이지가 입력창 없이 기능설명 화면으로 대체
- [ ] 리포트 생성 정상 동작 — 기본 날짜가 빈 리포트 아님
      (0501 또는 0518처럼 인사이트 있는 날짜가 기본값)
- [ ] 시간당 5건 제한 — 6번째 요청 시 차단 메시지 확인

## Render (실데이터 파일럿, 추후)
- Persistent Disk 마운트 경로를 DB_PATH로 지정
- APP_PASSWORD secret 설정 (비밀번호 게이트 활성화)
- DEMO_MODE 미설정 또는 false
- 파일럿 전용 OpenAI 키 (별도 스펜딩 캡)
- 헬리녹스 실 ERP 데이터 최초 적재: backfill_from_export.py