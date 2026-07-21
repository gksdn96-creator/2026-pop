import streamlit as st
import pandas as pd
import numpy as np
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

    # 지역명이 중복되는 경우(같은 이름의 동/읍/면 등)를 구분하기 위해 행정구역코드를 붙인 표시명 생성
    df["행정구역코드"] = df["행정구역"].str.extract(r"\((\d+)\)")
    dup_mask = df["지역명"].duplicated(keep=False)
    df["표시명"] = df["지역명"]
    df.loc[dup_mask, "표시명"] = df.loc[dup_mask, "지역명"] + " (" + df.loc[dup_mask, "행정구역코드"] + ")"

    return df.reset_index(drop=True)

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

# 연령별(계) 컬럼을 나이순으로 정렬
age_total_cols = []
for col in df.columns:
    m = age_pattern.match(col)
    if m and m.group(1) == "계":
        age_total_cols.append((parse_age(m.group(2)), col))
age_total_cols.sort()
ages_sorted = [a for a, _ in age_total_cols]
age_col_names = [c for _, c in age_total_cols]

# ------------------------------
# 3. 인구 비율(정규화) 행렬 계산 - 유사 지역 검색용
# ------------------------------
@st.cache_data
def compute_proportions(df, age_col_names):
    mat = df[age_col_names].to_numpy(dtype=float)
    row_sums = mat.sum(axis=1)
    props = np.zeros_like(mat)
    valid = row_sums > 0
    props[valid] = mat[valid] / row_sums[valid, None]
    return props, valid

props, valid_mask = compute_proportions(df, age_col_names)

# ------------------------------
# 4. 지역 검색 + 선택 (검색어 입력하면 목록이 좁혀짐)
# ------------------------------
region_list = df["표시명"].tolist()

col1, col2 = st.columns([1, 2])
with col1:
    search_text = st.text_input("🔍 지역 검색어 입력 (예: 강남, 수원, 해운대)", "")

filtered_regions = [r for r in region_list if search_text.strip() in r] if search_text.strip() else region_list

with col2:
    if filtered_regions:
        selected_display = st.selectbox(f"지역 선택 ({len(filtered_regions)}개)", filtered_regions)
    else:
        st.warning("검색 결과가 없습니다. 다른 검색어를 입력해보세요.")
        selected_display = None

# ------------------------------
# 5. 선택 지역 인구구조 꺾은선 그래프 (성별, 실제 인구수)
# ------------------------------
if selected_display:
    sel_idx = df.index[df["표시명"] == selected_display][0]
    row = df.loc[sel_idx]

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

    male_pop.sort(); female_pop.sort(); total_pop.sort()

    st.subheader(f"👤 {selected_display} 연령별 인구 구조 (실제 인구수)")

    fig1 = go.Figure()
    if total_pop:
        a, v = zip(*total_pop)
        fig1.add_trace(go.Scatter(x=a, y=v, mode="lines", name="전체", line=dict(color="#2ecc71", width=3)))
    if male_pop:
        a, v = zip(*male_pop)
        fig1.add_trace(go.Scatter(x=a, y=v, mode="lines", name="남성", line=dict(color="#3498db", width=2, dash="dot")))
    if female_pop:
        a, v = zip(*female_pop)
        fig1.add_trace(go.Scatter(x=a, y=v, mode="lines", name="여성", line=dict(color="#e74c3c", width=2, dash="dot")))

    fig1.update_layout(
        xaxis_title="연령(세)", yaxis_title="인구수(명)",
        hovermode="x unified", height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig1, use_container_width=True)

    m1, m2, m3 = st.columns(3)
    m1.metric("총 인구수", f"{int(row[total_col]):,} 명")
    m2.metric("남성 인구수", f"{int(row[f'{prefix}_남_총인구수']):,} 명")
    m3.metric("여성 인구수", f"{int(row[f'{prefix}_여_총인구수']):,} 명")

    st.divider()

    # ------------------------------
    # 6. 전국에서 인구구조가 가장 비슷한 Top 5 지역
    # ------------------------------
    st.subheader(f"🔎 '{selected_display}'와 인구 구조가 가장 비슷한 전국 Top 5 지역")
    st.caption("인구 규모 차이를 제거하기 위해 연령별 인구를 '비율(%)'로 정규화한 뒤, 형태가 가장 비슷한 지역을 찾았습니다. (읍·면·동 포함 전국 비교)")

    if not valid_mask[sel_idx]:
        st.warning("선택한 지역의 인구 데이터가 없어 유사 지역을 계산할 수 없습니다.")
    else:
        selected_vec = props[sel_idx]

        distances = np.sqrt(((props - selected_vec) ** 2).sum(axis=1))
        distances[~valid_mask] = np.inf
        distances[sel_idx] = np.inf  # 자기 자신 제외

        top5_idx = np.argsort(distances)[:5]

        result_df = pd.DataFrame({
            "지역": df.loc[top5_idx, "표시명"].values,
            "총인구수": df.loc[top5_idx, total_col].astype(int).values,
            "구조 거리(작을수록 유사)": distances[top5_idx].round(5),
        })
        st.dataframe(result_df, use_container_width=True, hide_index=True)

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=ages_sorted, y=selected_vec * 100, mode="lines",
            name=f"{selected_display} (선택 지역)",
            line=dict(color="black", width=4),
        ))

        palette = ["#e74c3c", "#3498db", "#f39c12", "#9b59b6", "#1abc9c"]
        for rank, idx in enumerate(top5_idx):
            fig2.add_trace(go.Scatter(
                x=ages_sorted, y=props[idx] * 100, mode="lines",
                name=f"{rank+1}위 · {df.loc[idx, '표시명']}",
                line=dict(color=palette[rank % len(palette)], width=1.8, dash="dash"),
            ))

        fig2.update_layout(
            xaxis_title="연령(세)", yaxis_title="비율(%)",
            hovermode="x unified", height=550,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig2, use_container_width=True)
