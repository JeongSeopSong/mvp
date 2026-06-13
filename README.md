# 사업 수익성 분석 프로그램

외식업, 물품판매업, 서비스업의 기본 사업성 가정을 빠르게 입력하고 화면에서 바로 결과를 확인하는 Streamlit 웹앱입니다.

## 주요 기능

- 외식업, 물품판매업, 서비스업 기본값 제공
- 사업명, 업종, 분석기간, 세율, 성장률, 초기투자비 입력
- 매출항목명 직접 입력
- 매출, 비용, 인력 항목 추가/삭제
- 키보드 수기 숫자 입력
- 대시보드에서 KPI, 차트, 손익계산서, 현금흐름, 손익분기점 확인
- 기본설정, 입력값, KPI, 대시보드 차트를 포함한 PDF 보고서 다운로드

## 로컬 실행

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

패키지 설치:

```bash
pip install -r requirements.txt
```

앱 실행:

```bash
streamlit run app.py
```

## Streamlit Community Cloud 배포

이 폴더(`business_profitability_mvp`)를 GitHub 저장소로 올린 뒤 Streamlit Community Cloud에서 배포합니다.

1. GitHub에 새 repository를 만듭니다.
2. 이 폴더 안의 파일을 repository 루트에 올립니다.
3. [Streamlit Community Cloud](https://share.streamlit.io/)에 로그인합니다.
4. `New app`을 누릅니다.
5. GitHub repository를 선택합니다.
6. Main file path에 `app.py`를 입력합니다.
7. Deploy를 누릅니다.

현재 배포에 필요한 파일:

```text
app.py
requirements.txt
.streamlit/config.toml
model/
utils/
README.md
```

`requirements.txt`는 앱 진입 파일인 `app.py`와 같은 폴더에 있어야 합니다.

## 주의사항

이 앱은 사업성 검토용 단순 모델입니다. 실제 투자 판단, 세무 신고, 회계 보고에는 업종별 회계처리, 부가세, 감가상각 내용연수, 차입금 상환 스케줄, 운전자본, 소득세/법인세 체계 등을 별도로 반영해야 합니다.
