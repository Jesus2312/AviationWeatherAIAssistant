"""deepeval LLM-quality tests for METAR chat answers.

Unlike the rest of the suite, these tests exercise the *real* agent end to
end -- real OpenAI-compatible model, real deepeval judge model -- so they
need OPENAI_API_KEY set and a reachable Redis (same as `docker compose up`
/ local `uvicorn` dev setup). Only the aviationweather.gov fetch is mocked
(via monkeypatch, not respx -- respx's global HTTP patching also intercepts
the real LLM/Langfuse traffic this test needs to go out for real, and its
pass-through mode mangles streamed responses), so each question gets a
deterministic, hand-crafted raw METAR to be decoded, and the judge has a
ground truth to grade against.

These are slow and cost real API calls, so they're tagged with the `eval`
marker and excluded from the default `pytest` run (see pytest.ini). Run
them explicitly with:

    pytest -m eval tests/test_metar_deepeval.py -v

or under deepeval's own runner:

    deepeval test run tests/test_metar_deepeval.py -m eval
"""

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.models import OpenAIModel
from deepeval.test_case import LLMTestCase, SingleTurnParams
from fastapi.testclient import TestClient

import app.tools.aviation_weather as aviation_weather
from app.config import get_settings
from app.main import app

pytestmark = pytest.mark.eval

# deepeval's judge model defaults to calling api.openai.com directly and
# only reads the standard OPENAI_API_KEY env var -- it does not know about
# this project's OPENAI_API_BASE (e.g. OpenRouter). Without this, the key
# meant for OPENAI_API_BASE gets sent to real OpenAI instead, which fails
# or hangs. Point the judge at the same provider/model the app itself uses.
_settings = get_settings()
_judge_model = OpenAIModel(
    model=_settings.openai_model,
    api_key=_settings.openai_api_key,
    base_url=_settings.openai_api_base or None,
)

# question, ICAO code, raw METAR text to serve back from the mocked
# aviationweather.gov endpoint for that ICAO.
CASES = [
    (
        "What's the current METAR for JFK?",
        "KJFK",
        "KJFK 151951Z 28012KT 10SM FEW250 24/12 A3012 RMK AO2 SLP198 T02440122",
    ),
    (
        "Can you give me the metar for Los Angeles International Airport?",
        "KLAX",
        "KLAX 151953Z 25008KT 8SM BKN012 18/14 A2995 RMK AO2 SLP140 T01780139",
    ),
    (
        "What are the current conditions at Chicago O'Hare?",
        "KORD",
        "KORD 151951Z 31015G25KT 4SM -RA BR OVC008 09/07 A2989 RMK AO2 SLP121 T00890072",
    ),
    (
        "Please decode the metar for Denver International.",
        "KDEN",
        "KDEN 151953Z 36022G30KT 10SM FEW060 SCT250 05/M08 A3001 RMK AO2 PK WND 36030/1925 SLP159 T00501083",
    ),
    (
        "What's the visibility and cloud cover at Atlanta Hartsfield?",
        "KATL",
        "KATL 151952Z 09006KT 10SM SCT035 BKN250 27/20 A3005 RMK AO2 SLP176 T02670200",
    ),
]


@pytest.fixture(scope="module")
def auth_token():
    # Module-scoped: app.agent's shared LLM httpx client, Langfuse client,
    # and Redis checkpointer are process-level singletons torn down by the
    # FastAPI lifespan's shutdown path (see app/main.py). A function-scoped
    # TestClient would run that shutdown after every parametrized case,
    # closing those singletons without recreating them -- later cases then
    # reuse a closed httpx client / shut-down Langfuse client, which doesn't
    # raise cleanly and instead hangs. One TestClient (one lifespan) for the
    # whole module avoids that.
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert response.status_code == 200
        yield response.json()["access_token"], client


@pytest.mark.parametrize("question, icao, raw_metar", CASES)
def test_metar_answer_quality(auth_token, monkeypatch, question, icao, raw_metar):
    token, client = auth_token

    async def fake_fetch(report_type: str, requested_icao: str) -> list:
        assert report_type == "metar"
        return [{"icaoId": icao, "rawOb": raw_metar}]

    monkeypatch.setattr(aviation_weather, "_fetch", fake_fetch)

    response = client.post(
        "/api/chat",
        json={"message": question},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    answer = response.json()["answer"]

    test_case = LLMTestCase(
        input=question,
        actual_output=answer,
        context=[raw_metar],
    )

    answer_relevancy = AnswerRelevancyMetric(threshold=0.7, model=_judge_model)
    decoding_accuracy = GEval(
        name="METAR Decoding Accuracy",
        model=_judge_model,
        criteria=(
            "Determine whether 'actual output' shows the raw METAR from "
            "'context' and correctly decodes every field present in it "
            "(report time, wind including gusts, visibility, weather "
            "phenomena, sky condition/ceiling, temperature and dewpoint, "
            "and altimeter setting) in plain English, without inventing "
            "any values that are not present in the raw METAR in 'context'."
        ),
        evaluation_params=[
            SingleTurnParams.INPUT,
            SingleTurnParams.ACTUAL_OUTPUT,
            SingleTurnParams.CONTEXT,
        ],
        threshold=0.7,
    )

    assert_test(test_case, [answer_relevancy, decoding_accuracy])
