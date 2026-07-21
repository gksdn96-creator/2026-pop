import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from pathlib import Path

st.set_page_config(page_title="지역별 연령별 인구 구조", layout="wide")

st.title("📊 지역별 연령별 인구 구조 보기")
st.caption("행정안전부 주민등록 연령별 인구현황(월간) CSV 파일 기반")

# ------------------------------
# 1. 데이터 로드 (코드와 같은 폴더의 CSV 파일)
# ------------------------------
DATA_FILE = Path(__file__).parent / "202606_202606_연령별인구현황_월간.csv"

@st.cache_data
def load_data(path):
    df = pd.read_csv(path, encoding="cp949", thousands=",")
    df["지역명"] = df["행정구역"].str.replace(r"\s*\(\d+\)\s*$", "", regex=True).str.strip()
    return df

if not DATA_FILE.exists():
    st.error(f"데이터 파일을 찾을 수 없습니다: {DATA_FILE.name}\n"
             f"app.py와 같은 폴더에 CSV 파일이 있는지 확인해주세요.")
    st.stop()

df = load_data(DATA_FILE)

# ------------------------------
# 2. 컬럼 자동 파싱 (기준 연월 자동 감지)
# ------------------------------
total_col = [c for c in df.columns if c.endswith("_계_총인구수")][0]
prefix = total_col.replace("_계_총인구수", "")  # 예: '2026년06월'

age_pattern = re.compile(rf"^{re.escape(prefix)}_(계|남|여)_(\d+세|100세 이상)$")

def parse_age(age_str):
    return 100 if age_str == "100세 이상" else int(age_str.replace("세", ""))

# ------------------------------
# 3. 지역 검색 + 선택 (검색어 입력하면 목록이 좁혀짐)
# ------------------------------
region_list = df["지역명"].tolist()

col1, col2 = st.columns([1, 2])
with col1:
    search_text = st.text_input("🔍 지역 검색어 입력 (예: 강남, 수원, 해운대)", "")

filtered_regions = [r for r in region_list if search_text.strip() in r] if search_text.strip() else region_list

with col2:
    if filtered_regions:
        selected_region = st.selectbox(f"지역 선택 ({len(filtered_regions)}개)", filtered_regions)
    else:
        st.warning("검색 결과가 없습니다. 다른 검색어를 입력해보세요.")
        selected_region = None

# ------------------------------
# 4. 선택 지역 인구구조 꺾은선 그래프
# ------------------------------
if selected_region:
    row = df[df["지역명"] == selected_region].iloc[0]

    male_pop, female_pop, total_pop = [], [], []

    for col in df.columns:
        m = age_pattern.match(col)
        if not m:
            continue
        gender, age_str = m.group(1), m.group(2)
        age = parse_age(age_str)
        value = row[col]

        if gender == "남":
            male_pop.append((age, value))
        elif gender == "여":
            female_pop.append((age, value))
        elif gender == "계":
            total_pop.append((age, value))

    male_pop.sort()
    female_pop.sort()
    total_pop.sort()

    fig = go.Figure()

    if total_pop:
        ages_t, vals_t = zip(*total_pop)
        fig.add_trace(go.Scatter(x=ages_t, y=vals_t, mode="lines", name="전체",
                                  line=dict(color="#2ecc71", width=3)))
    if male_pop:
        ages_m, vals_m = zip(*male_pop)
        fig.add_trace(go.Scatter(x=ages_m, y=vals_m, mode="lines", name="남성",
                                  line=dict(color="#3498db", width=2, dash="dot")))
    if female_pop:
        ages_f, vals_f = zip(*female_pop)
        fig.add_trace(go.Scatter(x=ages_f, y=vals_f, mode="lines", name="여성",
                                  line=dict(color="#e74c3c", width=2, dash="dot")))

    fig.update_layout(
        title=f"{selected_region} 연령별 인구 구조",
        xaxis_title="연령(세)",
        yaxis_title="인구수(명)",
        hovermode="x unified",
        height=600,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)

    # 요약 지표
    m1, m2, m3 = st.columns(3)
    m1.metric("총 인구수", f"{int(row[total_col]):,} 명")
    male_total_col = f"{prefix}_남_총인구수"
    female_total_col = f"{prefix}_여_총인구수"
    m2.metric("남성 인구수", f"{int(row[male_total_col]):,} 명")
    m3.metric("여성 인구수", f"{int(row[female_total_col]):,} 명")
