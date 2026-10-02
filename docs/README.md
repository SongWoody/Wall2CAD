# Wall2CAD 작업 문서

이 문서는 Git 저장소 안 `Wall2CAD/docs/`에 있으며, 프로젝트 목표와 사용자 결정,
수작업과 자동 추출의 관계, 기준본, 현재 편집기 상태, 다음 단계만 유지합니다.

## 지금 읽을 것

1. [현재 목표·파이프라인·다음 단계](PROJECT_STATUS.md)
2. [편집기 실행과 조작법](16_minimal_editor.md)
3. [겹침 표시 보정 기록](17_overlap_display_fix.md)

## 보존한 자료

- [사용자 요구와 검토 기준](decisions/requirements.md)
- [기준본 평가 요약](baselines/building_001_v1/acceptance.json)
- [319개 입력 윤곽 좌표](baselines/building_001_v1/candidates.json)
- [기준본 생성 조건](baselines/building_001_v1/plan.json)
- [기준본 처리 요약](baselines/building_001_v1/summary.json)
- [기준본 타일 재현 코드와 SAM 환경 안내](experiments/README.md)
- [사용자 원문 피드백과 정점 선호 선택](decisions/)
- [윤곽 샘플 선택 기록](decisions/stone_preferences.json)
- [정면 돌 경계 피드백](decisions/front_face_feedback.json)
- [최소 편집기 검증 기록](experiments/step06_editor/validation.json)
- [겹침 누락과 수정 후 계산 기록](experiments/step06_editor/overlap_validation.json)
- [편집기 화면 자료](assets/editor/)

개발 재개의 첫 작업은 편집기로 돌 일부를 고치고, 실제 수정 시간을 수작업과 비교해 적는 것입니다.
기준본을 직접 바꾸지 말고 **Save**로 별도 `.wall2cad.json` 편집본을 만드세요.

## 경로 배치

현장 사진·사람 작성 DXF는 회사 자료로 Git 저장소 바깥 `../inputoutput/`에 그대로 둡니다.
현장 사진은 Git에 추가하지 않습니다. `--sample` 실행에는 `building_001_input.jpeg`와
보존한 기준본 `candidates.json`이 필요합니다.

```text
작업 폴더/
├── inputoutput/                  # 원본 현장 자료, Git 바깥
│   ├── building_001_input.jpeg
│   └── building_001_target.dxf
└── Wall2CAD/                     # 이 저장소
    ├── docs/                     # 프로젝트 문서와 비민감한 기준 윤곽 좌표
    ├── contour_editor/
    └── run_editor.command
```

이 폴더에는 예전 중간 마스크, 임시 로그, 중복 CAD 묶음, 수동 수정 제안 산출물,
만료된 임시 가상환경 경로를 안내하던 보고서는 포함하지 않았습니다.
