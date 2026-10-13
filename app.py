import streamlit as st
import pandas as pd

# ==========================================
# 0. ページ設定
# ==========================================
st.set_page_config(
    page_title="ニノクロ イマージェン編成バフシミュレーター",
    page_icon="🐾",
    layout="wide"
)

st.title("🐾 ニノクロ イマージェン編成バフシミュレーター")
st.write("スプレッドシートと連携し、2つの編成の常時バフ・条件付きバフを比較・シミュレーションします。")

# ==========================================
# 1. スプレッドシートからのデータ読み込み
# ==========================================
# ★ご自身のスプレッドシート情報に書き換えてください
SHEET_URL = "https://docs.google.com/spreadsheets/d/1wRhQf40PgWSMd8ZgqqP6f3QWNR9vqS8HLlyDOT95OD8/edit?usp=sharing"
GID_MASTER = "0"
GID_EFFECTS = "1688437536"  # 効果データタブのgid

@st.cache_data(ttl=600)
def load_data():
    try:
        sheet_id = SHEET_URL.split('/d/')[1].split('/')[0]
        url_master = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={GID_MASTER}"
        url_effects = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={GID_EFFECTS}"
        
        df_master = pd.read_csv(url_master)
        df_effects = pd.read_csv(url_effects)
        df_master.columns = df_master.columns.astype(str).str.strip()
        df_effects.columns = df_effects.columns.astype(str).str.strip()
        return df_master, df_effects
    except Exception as e:
        st.error(f"データ読み込みエラー: {e}")
        return None, None

df_master, df_effects = load_data()

if df_master is not None and df_effects is not None:
    imagen_pedia = {}
    display_to_id = {}
    temp_list = []
    attr_order = {"火": 1, "水": 2, "木": 3, "光": 4, "闇": 5}

    for _, row in df_master.iterrows():
        img_id = str(row['イマージェンID']).strip()
        name = str(row['名前']).strip()
        attr = str(row['属性']).strip()
        itype = str(row['タイプ']).strip()
        
        imagen_pedia[img_id] = {
            "名前": name, "属性": attr, "タイプ": itype, "効果": []
        }
        attr_sort_key = attr_order.get(attr, 99)
        temp_list.append((attr_sort_key, attr, name, img_id))

    # 属性順 ➔ 名前順でソート
    temp_list.sort(key=lambda x: (x[0], x[2]))

    sorted_display_names = []
    for _, attr, name, img_id in temp_list:
        display_name = f"【{attr}】 {name}"
        sorted_display_names.append(display_name)
        display_to_id[display_name] = img_id

    for _, row in df_effects.iterrows():
        img_id = str(row['イマージェンID']).strip()
        if img_id in imagen_pedia:
            values_dict = {}
            for col in df_effects.columns:
                col_str = str(col).strip()
                if col_str.startswith('覚醒'):
                    level_str = col_str.replace('覚醒', '')
                    val = row[col]
                    values_dict[level_str] = float(val) if pd.notna(val) else None
            
            target_raw = str(row['対象']).strip() if '対象' in row and pd.notna(row['対象']) else '固定'
            cond_raw = str(row['条件']).strip() if '条件' in row and pd.notna(row['条件']) else None
            stat_raw = str(row['ステータス']).strip() if 'ステータス' in row and pd.notna(row['ステータス']) else ''
            
            imagen_pedia[img_id]["効果"].append({
                "対象": target_raw, "条件": cond_raw, "ステータス": stat_raw, "数値リスト": values_dict
            })

    # 計算ロジック
    def get_effect_value(values_dict, awakening_level):
        current_value = 0.0
        for key_level in sorted(map(int, values_dict.keys())):
            if awakening_level >= key_level:
                val = values_dict[str(key_level)]
                if val is not None: current_value = val
            else: break
        return current_value

    def calculate_team_buffs(selected_team, pedia):
        attr_counts, type_counts = {}, {}
        for item in selected_team:
            info = pedia[item["id"]]
            attr_counts[info["属性"]] = attr_counts.get(info["属性"], 0) + 1
            type_counts[info["タイプ"]] = type_counts.get(info["タイプ"], 0) + 1

        always_buffs, cond_buffs = {}, {}
        for item in selected_team:
            info = pedia[item["id"]]
            awakening = item["覚醒"]
            for effect in info["効果"]:
                val = get_effect_value(effect["数値リスト"], awakening)
                if val == 0.0: continue
                
                target, cond, stat = effect["対象"], effect["条件"], effect["ステータス"]
                multiplier = 1
                if target == "属性" and cond:
                    multiplier = sum(attr_counts.get(c.strip(), 0) for c in cond.split('/'))
                elif target == "タイプ" and cond:
                    multiplier = sum(type_counts.get(c.strip(), 0) for c in cond.split('/'))
                
                total_val = val * multiplier
                if target == "状況" or (cond and target not in ["属性", "タイプ"]):
                    cond_label = f"[{cond}] {stat}"
                    cond_buffs[cond_label] = cond_buffs.get(cond_label, 0.0) + total_val
                else:
                    always_buffs[stat] = always_buffs.get(stat, 0.0) + total_val

        return always_buffs, cond_buffs, attr_counts, type_counts

    # ==========================================
    # 2. Streamlit 画面レイアウト（2カラム比較）
    # ==========================================
    col1, col2 = st.columns(2)

    def render_team_inputs(column_title, prefix):
        st.subheader(column_title)
        team_data = []
        for i in range(3):
            cols = st.columns([3, 1])
            with cols[0]:
                selected_name = st.selectbox(f"{prefix} {i+1}体目", sorted_display_names, index=i if i < len(sorted_display_names) else 0, key=f"{prefix}_name_{i}")
            with cols[1]:
                awakening = st.number_input("覚醒", min_value=0, max_value=30, value=10, step=1, key=f"{prefix}_awk_{i}")
            team_data.append({"id": display_to_id[selected_name], "覚醒": awakening})
        return team_data

    with col1:
        teamA_data = render_team_inputs("🔵 編成 A", "A")

    with col2:
        teamB_data = render_team_inputs("🔴 編成 B", "B")

    st.markdown("---")

    if st.button("⚔️ 2つの編成を比較する", type="primary", use_container_width=True):
        alwaysA, condA, attrsA, typesA = calculate_team_buffs(teamA_data, imagen_pedia)
        alwaysB, condB, attrsB, typesB = calculate_team_buffs(teamB_data, imagen_pedia)

        st.success("計算が完了しました！")

        # 比較結果テーブルの作成
        all_stats = sorted(list(set(alwaysA.keys()) | set(alwaysB.keys())))
        comparison_rows = []
        for stat in all_stats:
            valA = alwaysA.get(stat, 0.0)
            valB = alwaysB.get(stat, 0.0)
            diff = valB - valA
            diff_str = f"+{diff:.1f}%" if diff > 0 else (f"{diff:.1f}%" if diff < 0 else "±0.0%")
            winner = "Bが優勢 🔴" if diff > 0 else ("Aが優勢 🔵" if diff < 0 else "互角 -")
            
            comparison_rows.append({
                "ステータス": stat,
                "編成 A": f"+{valA:.1f}%",
                "編成 B": f"+{valB:.1f}%",
                "差分 (B - A)": diff_str,
                "優勢": winner
            })

        st.markdown("### 📊 常時バフ比較結果")
        if comparison_rows:
            df_result = pd.DataFrame(comparison_rows)
            st.table(df_result)
        else:
            st.info("常時発動するバフがありません。")

        # 条件付きバフの表示
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            st.markdown("#### 🔵 編成 A：条件・状況付きバフ")
            if condA:
                for k, v in condA.items():
                    st.write(f"- {k}: **+{v:.1f}%**")
            else:
                st.write("なし")

        with col_res2:
            st.markdown("#### 🔴 編成 B：条件・状況付きバフ")
            if condB:
                for k, v in condB.items():
                    st.write(f"- {k}: **+{v:.1f}%**")
            else:
                st.write("なし")