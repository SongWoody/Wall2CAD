# Wall2CAD

문화재 토목기술자를 위한 AI 기반 벽돌 분석 및 CAD 변환 도구

## 최소 윤곽 편집기 (2026-10-02)

현재 개발 진입점은 `contour_editor`입니다. 사진과 이미 추출한 돌 좌표를 불러와
정점 이동·추가·삭제, 돌 삭제, 실행 취소·다시 실행, 프로젝트 저장·재열기,
닫힌 폴리라인 DXF 출력을 할 수 있습니다. SAM 추론은 실행하지 않습니다.
기존 두 GUI와 독립적으로 실행되며, 아래의 과거 프로젝트 소개에는 계획 단계의 기능도 포함돼 있습니다.

Python 3.12 환경에서 설치·실행합니다. 편집기에는 GPU나 모델 가중치가 필요하지 않습니다.

```bash
# macOS / Linux — 이 README가 있는 Git 저장소에서 실행
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-editor.txt
.venv/bin/python -m contour_editor
```

```powershell
# Windows — 이 README가 있는 Git 저장소에서 실행
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-editor.txt
.venv\Scripts\python.exe -m contour_editor
```

현재 작업 폴더의 합격 기준본을 열려면 `--sample`을 붙이세요.
설치 후 macOS의 `run_editor.command`, Windows의 `run_editor.bat`을 더블클릭해도
같은 기준본이 열립니다. 기준본은 Git에 포함하지 않으며 다음 형제 폴더 배치가 필요합니다.

```text
작업폴더/
├── inputoutput/building_001_input.jpeg
├── docs/baselines/building_001_v1/candidates.json
└── Wall2CAD/  ← 이 Git 저장소
```

다른 사진·윤곽은 화면의 **사진 + 윤곽 열기** 또는 다음 명령으로 엽니다.
후보 JSON은 `[{"id": "S001", "points": [[x, y], ...]}, ...]` 형태이며,
좌표는 원본 사진의 왼쪽 위가 원점인 픽셀 단위입니다. 현재 좌표로 겹침을 계산해
겹친 돌은 주황색, 실제 겹친 영역은 빨간색으로 표시합니다. 기존 JSON의 `layer`와
`overlap_with`는 원래 추출 기록으로 보존하며, 현재 겹침 판정에는 사용하지 않습니다.

```bash
.venv/bin/python -m contour_editor --image /path/photo.jpeg --contours /path/candidates.json
.venv/bin/python -m contour_editor /path/review.wall2cad.json
```

- 돌 클릭으로 선택, 왼쪽 목록 더블클릭으로 해당 돌 확대.
- 정점을 드래그하여 이동, 선택 돌의 선 더블클릭으로 정점 추가.
- 정점 클릭 후 Delete/Backspace로 삭제. 돌 전체는 **돌 삭제** 버튼 사용.
- 휠로 확대, Space+드래그 또는 가운데 버튼으로 이동, F로 전체 보기.
- **선택 돌 원본 비교**를 켜면 원래 윤곽이 분홍 점선으로 표시됩니다.
- 선택 돌의 겹치는 상대 번호를 목록 아래에서 확인할 수 있습니다. 작은 면적 겹침도 표시하며, 경계끼리 닿기만 하는 경우는 제외합니다. 편집 확정·삭제·Undo/Redo 시 표시와 DXF 레이어를 갱신합니다.
- 프로젝트는 `.wall2cad.json`으로 저장합니다. 원본 좌표·편집 좌표·삭제 상태를 보존하며 사진은 별도 파일로 유지합니다.
- DXF는 픽셀 좌표/단위 없음입니다. `x = 사진 x`, `y = 사진 높이 - 사진 y`로 출력하며 실측 좌표 정합은 별도입니다.

실행 취소 이력은 현재 세션에서만 유지합니다. DXF 출력은 프로젝트 저장을 대신하지 않습니다.
현재 macOS에서 검증했으며 Windows 실기기 및 AutoCAD에서의 편집본 검수는 아직 진행하지 않았습니다.
상세 검증·사용 안내는 저장소 밖 `../docs/16_minimal_editor.md`에 있습니다.

```bash
# 개발 검증 — Windows에서는 .venv\Scripts\python.exe 사용
.venv/bin/python -m pip install -r requirements-editor-dev.txt
.venv/bin/python -m pytest tests/editor -q
```

샘플 통합 테스트는 위 형제 폴더에 기준본이 있을 때만 실행합니다.

## 프로젝트 개요

Wall2CAD는 문화재 토목 기술 분야에서 건축용 벽 이미지를 정밀하게 분석하여 각 벽돌의 외곽선을 자동으로 감지하고, 이를 벡터 데이터로 변환한 후 CAD 소프트웨어에서 바로 사용할 수 있는 DXF 파일로 내보내는 전문 도구입니다.

## 프로젝트 배경 및 목적

### 문제 인식
문화재 토목기술자들이 건축물의 벽면을 도면화할 때 겪는 주요 어려움:
- **수작업의 한계**: 복잡한 벽돌 패턴을 일일이 측정하고 그리는 시간 소요
- **정확성 문제**: 사진에서 CAD로 옮기는 과정에서 발생하는 오차
- **효율성 부족**: 대량의 벽면 데이터를 처리하는데 필요한 인력과 시간

### 해결 방안
최신 AI 기술(SAM - Segment Anything Model)을 활용하여:
- **자동화된 벽돌 감지**: 이미지에서 각 벽돌의 경계를 정확히 식별
- **정밀한 벡터화**: 픽셀 데이터를 정확한 벡터 좌표로 변환
- **CAD 호환성**: 업계 표준 DXF 형식으로 직접 내보내기

## 주요 기능

### 🎯 정밀한 벽돌 경계 감지
- SAM AI 모델을 사용한 자동 객체 분할
- 복잡한 벽돌 패턴도 개별적으로 정확하게 인식
- 그림자, 이음새, 손상된 부분까지 고려한 지능적 분석

### 📐 벡터 데이터 변환
- 픽셀 기반 마스크를 정확한 벡터 좌표로 변환
- 각 벽돌별 외곽선을 폴리라인으로 생성
- 좌표계 변환으로 실제 측정값에 맞는 스케일 적용

### 💾 CAD 호환 DXF 출력
- AutoCAD, SolidWorks 등 주요 CAD 소프트웨어와 완벽 호환
- 벽돌 크기, 품질별 자동 레이어 분류
- 도면 작업에 즉시 활용 가능한 형태로 출력

## 프로젝트 구조

```
Wall2CAD/
├── README.md                    # 프로젝트 전반 설명 (이 파일)
├── .gitignore                   # Git 제외 파일 설정
├── wall2cad_mvp/               # MVP 애플리케이션
│   ├── README.md               # MVP 상세 사용법
│   ├── main.py                 # 애플리케이션 진입점
│   ├── ui_main.py              # 사용자 인터페이스
│   ├── sam_processor.py        # AI 모델 처리
│   ├── dxf_converter.py        # DXF 변환 엔진
│   ├── requirements.txt        # 의존성 목록
│   └── sam_vit_h_4b8939.pth   # SAM 모델 (별도 다운로드)
├── mvpprd.md                   # MVP 제품 요구사항
├── prd.md                      # 전체 제품 요구사항
└── rnd.md                      # 연구개발 노트
```

## 사용 시나리오

### 1. 문화재 복원 프로젝트
- 역사적 건축물의 벽면 패턴 정확한 기록
- 손상된 부분의 원형 복원을 위한 도면 작성
- 보존 상태 모니터링용 정밀 측정 데이터 구축

### 2. 건축 도면 작성
- 기존 건축물의 리모델링을 위한 현황 도면 생성
- 복잡한 벽돌 패턴의 시공 도면 작성
- 구조 분석을 위한 정확한 치수 측정

### 3. 연구 및 분석
- 건축 양식 연구를 위한 패턴 데이터 수집
- 시대별, 지역별 벽돌 쌓기 기법 비교 분석
- 구조적 안전성 평가를 위한 기초 데이터 생성

## 기술 스택

### AI/ML
- **SAM (Segment Anything Model)**: Meta에서 개발한 최첨단 객체 분할 모델
- **PyTorch**: 딥러닝 프레임워크
- **OpenCV**: 이미지 처리 및 컴퓨터 비전

### 벡터화 처리
- **NumPy**: 수치 계산 및 좌표 변환
- **Matplotlib**: 데이터 시각화 및 결과 미리보기

### CAD 출력
- **ezDXF**: 산업 표준 DXF 파일 생성
- 레이어 관리 및 좌표계 변환 최적화

### 사용자 인터페이스
- **PyQt5**: 전문가용 데스크톱 인터페이스
- **멀티스레딩**: 대용량 이미지 처리 중 UI 응답성 유지

## 현재 개발 상태

### ✅ 완료된 기능 (MVP)
- [x] SAM 모델 통합 및 자동 분할
- [x] 실시간 처리 결과 미리보기
- [x] DXF 파일 생성 및 내보내기
- [x] 사용자 친화적 GUI 인터페이스
- [x] 다양한 이미지 형식 지원

## 처리 예시

### 문화재 벽면 분석 결과
다음은 실제 문화재 석벽을 Wall2CAD로 처리한 결과입니다:

**원본 이미지**
![원본 석벽 이미지](sample/SampleImgag_Section_1.jpg)

**AI 분할 결과 (182개 마스크 감지)**
![처리 결과](sample/SampleImgag_Section_1_Result.jpg)

Wall2CAD는 복잡한 석벽 패턴에서도 개별 돌블록을 정확히 식별하여 각각을 별도의 벡터 객체로 변환합니다. 이 결과는 DXF 파일로 내보내져 AutoCAD 등 CAD 소프트웨어에서 바로 활용할 수 있습니다.

### 🚧 개발 중인 기능
- [ ] 배치 처리 (여러 이미지 동시 처리)
- [ ] 정밀도 향상을 위한 수동 보정 도구
- [ ] 실제 치수 입력 및 스케일 자동 조정
- [ ] 벽돌 유형별 자동 분류

### 🔮 향후 계획
- [ ] 3D 벽면 모델링 지원
- [ ] 클라우드 기반 협업 기능
- [ ] 모바일 앱 연동
- [ ] BIM(Building Information Modeling) 호환

## 설치 및 사용

### 빠른 시작
1. **저장소 복제**
   ```bash
   git clone https://github.com/your-repo/Wall2CAD.git
   cd Wall2CAD/wall2cad_mvp
   ```

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **SAM 모델 다운로드**
   ```bash
   # Hugging Face에서 다운로드 (2.5GB)
   pip install huggingface_hub
   python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='facebook/sam-vit-huge', filename='sam_vit_h_4b8939.pth', local_dir='.')"
   ```

4. **애플리케이션 실행**
   ```bash
   python main.py
   ```

상세한 사용법은 [MVP README](./wall2cad_mvp/README.md)를 참조하세요.

## 시스템 요구사항

### 최소 사양
- **OS**: Windows 10+, macOS, Linux
- **RAM**: 8GB 이상 (16GB 권장)
- **저장공간**: 5GB 이상 (모델 파일 포함)
- **Python**: 3.7 이상

### 권장 사양
- **GPU**: CUDA 지원 GPU (처리 속도 향상)
- **RAM**: 16GB 이상
- **CPU**: 멀티코어 프로세서

## 성능 최적화 팁

### 이미지 전처리
- **해상도**: 2000x2000 픽셀 이하 권장
- **형식**: JPEG 또는 PNG (압축률과 품질 균형)
- **조명**: 균일한 조명 조건에서 촬영된 이미지

### 하드웨어 활용
- **GPU 가속**: CUDA 설치로 처리 속도 10배 향상
- **메모리 관리**: 대용량 이미지는 분할 처리 권장

## 기여하기

이 프로젝트는 문화재 보존과 건축 기술 발전을 위해 개발되었습니다. 
기여를 환영하며, 특히 다음 분야의 전문가들의 참여를 기다립니다:

- 문화재 토목/건축 기술자
- 컴퓨터 비전 연구자
- CAD 소프트웨어 개발자
- 건축사 및 구조 엔지니어

## 라이센스

이 프로젝트는 MIT 라이센스 하에 배포됩니다. 교육, 연구, 상업적 목적으로 자유롭게 사용 가능합니다.

## 지원 및 문의

- **프로젝트 이슈**: GitHub Issues 페이지 활용
- **기술적 문의**: 코드 관련 질문 및 버그 리포트
- **협업 제안**: 연구기관, 문화재청 등과의 협력 가능

---

**"전통을 보존하는 혁신적 기술"** - 문화재 토목기술자를 위한 AI 도구

*이 프로젝트는 한국의 소중한 문화재 보존과 건축 기술 발전을 위해 개발되었습니다.*
