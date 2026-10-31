import os

import requests
import streamlit as st
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field


# 1. 수업 59~62쪽: .env에서 키를 읽고 화면을 준비한다.
load_dotenv()
st.set_page_config(page_title="환율 데스크", page_icon="💱")
st.markdown("""
<style>
.fx-ticket {
    position:relative; overflow:hidden; padding:clamp(1.5rem,5vw,3rem);
    margin-bottom:1.25rem; border-radius:1.25rem; background:#113e39;
    color:#f8faf0; border-top:5px solid #b9e48e;
}
.fx-ticket .fx-label {margin:0; color:#c4e7ae; font:700 .76rem monospace; letter-spacing:.16em}
.fx-ticket h1 {color:#fffdf1; margin:.65rem 0; padding:0; font-size:clamp(2.1rem,6vw,3.2rem); letter-spacing:-.055em}
.fx-ticket p {margin:0; color:#dfede1; word-break:keep-all}
.fx-ticket .fx-stamp {
    position:absolute; right:2rem; top:50%; transform:translateY(-50%) rotate(-8deg);
    width:7rem; height:7rem; border:4px double #9dc4a6; border-radius:50%;
    display:grid; align-content:center; text-align:center; color:#c4e7ae;
    font:700 .68rem monospace; letter-spacing:.12em;
}
.fx-stamp strong {display:block; font:italic 2.2rem Georgia,serif; letter-spacing:0}
@media (max-width:650px) {.fx-ticket .fx-stamp {display:none}}
</style>
<section class="fx-ticket">
  <p class="fx-label" lang="en">FX / EXCHANGE DESK</p>
  <h1>환율 데스크</h1>
  <p>얼마를, 어떤 통화로 바꿀까요?</p>
  <span class="fx-stamp" aria-hidden="true">CURRENCY<strong>FX</strong>EXCHANGE</span>
</section>
""", unsafe_allow_html=True)
st.caption("Frankfurter 제공  ·  최신 일별 기준 환율  ·  환전 수수료 미포함")


# 2. 앞서 배운 구조화된 출력: 질문에서 계산에 필요한 세 값만 읽는다.
class ExchangeRequest(BaseModel):
    base: str | None = Field(description="바꿀 통화의 영문 코드. 불분명하면 null")
    quote: str | None = Field(description="받을 통화의 영문 코드. 불분명하면 null")
    amount: float = Field(description="바꿀 금액. 단위 환율만 물으면 1")


def get_exchange_rate(base, quote):
    response = requests.get(
        f"https://api.frankfurter.dev/v2/rate/{base}/{quote}",
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data["rate"], data["date"]


def answer_question(messages):
    model = init_chat_model("gpt-5.4-mini")
    reader = model.with_structured_output(ExchangeRequest)
    instruction = (
        "마지막 사용자 질문에서 금액과 두 통화의 ISO 코드를 추출하세요. "
        "앞 대화를 명확히 이어가는 질문이면 이전 통화를 참고하세요. "
        "환율 질문이 아니거나 통화가 모호하면 해당 코드를 null로 두세요. "
        "금액에서 만, 천 같은 단위를 숫자로 환산하세요."
    )
    order = reader.invoke([{"role": "system", "content": instruction}, *messages])
    if not order.base or not order.quote:
        return "어떤 통화를 어떤 통화로 바꿀까요? 예: 100달러를 원화로"
    base, quote = order.base.upper(), order.quote.upper()
    if not all(len(code) == 3 and code.isascii() and code.isalpha() for code in (base, quote)):
        return "통화를 확인해 주세요. 예: USD를 KRW로"
    if order.amount < 0:
        return "환산할 금액은 0 이상으로 입력해 주세요."
    if base == quote:
        return f"같은 통화이므로 {order.amount:,g} {quote}입니다."

    rate, date = get_exchange_rate(base, quote)
    converted = order.amount * rate
    return (
        f"{order.amount:,g} {base} 환산 금액\n\n"
        f"### {converted:,.2f} {quote}\n\n"
        f"1 {base} = {rate:,} {quote}  ·  기준일 {date}"
    )


# 3. 수업 47~53쪽: 질문을 받고 세션에 대화 기록을 저장한다.
if "messages" not in st.session_state:
    st.session_state.messages = []

example = None
welcome = st.empty()
if not st.session_state.messages:
    with welcome.container():
        st.subheader("예시로 시작하기")
        left, right = st.columns(2)
        if left.button("100달러 → 원화", use_container_width=True):
            example = "100달러는 원화로 얼마야?"
        if right.button("1만 엔 → 원화", use_container_width=True):
            example = "1만 엔은 원화로 얼마야?"

prompt = st.chat_input("예: 50유로는 원화로 얼마야?") or example
if prompt:
    welcome.empty()
    st.session_state.messages.append({"role": "user", "content": prompt})
    if not os.getenv("OPENAI_API_KEY"):
        answer = "프로젝트의 .env 파일에 OPENAI_API_KEY를 설정해 주세요."
    else:
        try:
            with st.spinner("조회 중…"):
                answer = answer_question(st.session_state.messages)
        except requests.RequestException:
            answer = "환율을 조회하지 못했습니다. 통화 코드와 인터넷 연결을 확인해 주세요."
        except Exception:
            answer = "답변을 처리하지 못했습니다. 모델 접근 권한과 API 키를 확인해 주세요."
    st.session_state.messages.append({"role": "assistant", "content": answer})

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
