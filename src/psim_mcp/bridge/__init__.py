"""브리지(``bridge_script.py``, PSIM 번들 Python 3.8/3.9) 통신 공용 상수.

``bridge_script.py``는 이 패키지를 import하지 않는다(별도 인터프리터에서 스크립트로 실행).
"""

# 브리지 응답은 JSON 한 줄이다. asyncio StreamReader 기본 한도(64 KiB)로는 원본 해상도 파형
# (예: FFT용 수만 점 + times) 응답이 한 줄을 넘겨 LimitOverrunError가 난다.
# 상한 추정: 65,536점 × 2(값 + times) × 약 25 B ≈ 3.3 MB → 여유 있게 32 MiB.
STREAM_LIMIT = 32 * 1024 * 1024
