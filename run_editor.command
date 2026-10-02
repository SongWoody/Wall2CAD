#!/bin/zsh
set -e
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print '편집기 환경을 먼저 설치하세요. README의 최소 윤곽 편집기 항목을 확인하세요.'
  read '?Enter 키를 누르면 닫힙니다.'
  exit 1
fi
if (( $# == 0 )); then
  set -- --sample
fi
exec .venv/bin/python -m contour_editor "$@"
