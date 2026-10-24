"""API-07: 실제 응답 Provider·Model 확인
새 호출 없음 - API-02, API-03에서 이미 받아둔 응답을 재사용해서 필드만 확인.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

RAW_DIR = Path(__file__).resolve().parent.parent / "results" / "raw"

# 1. API-02 응답(요청 시 지정한 모델과 실제 응답 모델/provider 비교)
api02 = json.loads((RAW_DIR / "api02_response.json").read_text(encoding="utf-8"))
requested_model = "mistralai/mistral-nemo"  # API-02 요청 시 지정한 값
actual_model = api02.get("model")
actual_provider = api02.get("provider")

# 2. API-03(/generation) 응답에는 provider_responses 배열로 더 자세한 정보가 있음 -> 같이 비교
api03 = json.loads((RAW_DIR / "api03_response_1st.json").read_text(encoding="utf-8"))["data"]
provider_name_detail = api03.get("provider_name")
provider_responses = api03.get("provider_responses")

# 3. 요약 저장 (새 API 호출이 없으니 요청/응답 파일이 아니라 분석 결과만 저장)
summary = {
    "requested_model": requested_model,
    "chat_completion_response.model": actual_model,
    "chat_completion_response.provider": actual_provider,
    "generation_lookup.provider_name": provider_name_detail,
    "generation_lookup.provider_responses": provider_responses,
    "model_matches_request": actual_model == requested_model,
}
(RAW_DIR / "api07_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)

print("요청한 모델:", requested_model)
print("응답 model 필드:", actual_model)
print("응답 provider 필드:", actual_provider)
print("/generation 조회의 provider_name:", provider_name_detail)
print("모델 일치 여부:", summary["model_matches_request"])
