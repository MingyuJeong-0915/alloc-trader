# ALLOC — 자산배분 자동 투자 트래커

매주 금요일 자동으로 신호를 계산하고 추천 비중을 업데이트하는 자산배분 투자 트래커입니다.

## 구조
- `update_data.py` — 매주 실행되는 신호 계산 스크립트
- `docs/index.html` — 웹 대시보드
- `docs/data.json` — 자동 업데이트되는 시장 데이터
- `.github/workflows/update.yml` — 매주 금요일 자동 실행

## 자산 및 신호
- **자산**: SPY (주식) / GLD (금) / TLT (채권) / SHY (현금)
- **신호**: 실질금리 · 크레딧 스프레드 · DXY 달러 · VIX 변동성
