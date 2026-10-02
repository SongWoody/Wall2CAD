# 저장한 실험 자료와 재현 방법

새 작업을 시작할 때는 먼저 [프로젝트 상태와 다음 단계](../PROJECT_STATUS.md)를 읽습니다.
작은 검증 자료는 아래에 남겼습니다.

## 합격 기준본

`../baselines/building_001_v1/`에는 2026-10-01 전체 사진 초안에서 나온 319개 폴리곤 좌표,
사용자 정성 평가, 타일 설정과 실행 요약만 보존했습니다. 좌표 기준본은 이후 실험이 덮어쓰지 않습니다.
실제 현장 원본은 저장소 밖 `../../inputoutput/`에 있습니다.

## SAM 1 타일 실험 재현

`reproduce_full_image.py`는 시험 당시 SAM 1 ViT-B + 겹치는 가로 타일 처리를 실행하고
사진 픽셀 좌표 윤곽과 DXF를 생성합니다. 13,788 × 2,574 단일 가로 사진을 위해 작성한
실험 스크립트로, 범용 추론 인터페이스는 아닙니다.

원본 입력은 저장소 밖 `../../inputoutput/building_001_input.jpeg`, 기준 마스크 캐시는
`full_image_cache/tiles/`에 둡니다. 새 추론도 같은 캐시에 이어 기록합니다.
새 산출물은 `full_image_reproduction_output/`, 시각화는 `../assets/full_image_reproduction/`에 기록되며,
생성 폴더는 `.gitignore`에 있어 accepted baseline과 섞이지 않습니다.
모델 체크포인트는 별도로 내려받아 사용자 지정 경로에 두세요. 체크포인트를 Git에 넣지 않습니다.

기존 시험 환경 동결 목록은 `full_image_cache/requirements-freeze.txt`입니다.
이는 당시 macOS / Python 3.12 환경 기록이며 설치된 모든 패키지가 지금 플랫폼에서
설치 가능하다고 보장하지 않습니다. 스크립트는 저장소의 `wall2cad_mvp/segment_anything` 코드를 사용합니다.

예시 (환경에 맞는 독립적인 Python 3.12 환경과 SAM 체크포인트를 먼저 준비):

```bash
.venv-sam/bin/python docs/experiments/reproduce_full_image.py \
  --checkpoint /path/to/sam_vit_b_01ec64.pth --stage all
```

단계는 `plan`, `infer`, `finalize`, `all`을 받습니다. 같은 입력·모델·설정이면 저장된 타일 마스크를 다시 사용합니다.
이전 합격 산출물은 `baselines/`에 따로 보존합니다. 모델 재추론을 하려면 체크포인트와 PyTorch가 필요하며,
기준본을 여는 데는 추가 추론이 필요하지 않습니다.

## 최소 편집기 검증

`step06_editor/validation.json`에는 사진·후보 기준본의 해시와 편집/DXF 왕복 검증 요약이 있습니다.
`overlap_validation.json`에는 S091–S093, S093–S095의 면적 교차와 현재 기준본 전체 집계가 있습니다.
실제 자동 검증 DXF와 인위적인 수정 프로젝트는 결과물이므로 커밋하지 않았습니다.
