"""
世界杯小组出线博彩赔率数据清洗脚本
适用于：resources/data/football/odds-worldcup-group-2022.csv

将以下 CLEAN_SCRIPT 存入 data_src.clean_script 字段即可。
需配置 data_src.cleaned_path 如：data/worldcup/cleaned/odds-group-{year}.json
需配置 data_src.cleaned_name 如：odds-group-{year}
"""

CLEAN_SCRIPT = r'''
# 1. 解析 file_path 为绝对路径（使用 resolve_raw_path 确保与项目根一致）
full_path = resolve_raw_path(file_path)
if not full_path.is_file():
    raise FileNotFoundError(f"Raw file not found: {full_path}")

raw_text = full_path.read_text(encoding="utf-8-sig")

# 2. 美式赔率 -> 隐含概率
def american_odds_to_implied_prob(odds_str):
    if not odds_str or not str(odds_str).strip():
        return 0.5
    import re
    s = str(odds_str).strip().replace(",", "")
    m = re.match(r"([+-]?\d+)", s)
    if not m:
        return 0.5
    try:
        odds = int(m.group(1))
        if odds > 0:
            return 100 / (100 + odds)
        return abs(odds) / (abs(odds) + 100)
    except (ValueError, TypeError):
        return 0.5

# 3. 解析多行表头 CSV
lines = [r for r in raw_text.strip().split("\n") if r.strip()]
if len(lines) < 3:
    raise ValueError("CSV too short")

import csv
header_row = lines[1]
cols = next(csv.reader([header_row]))
col_map = {c.strip(): i for i, c in enumerate(cols)}
od_names = ["Sep 27,2020", "Jun 15,2022", "Nov 20,2022", "Game 2", "Game 3"]
od_cols = []
for k in od_names:
    for ck in col_map:
        if k in ck or k.replace(" ", "") in ck.replace(" ", ""):
            od_cols.append(ck)
            break
    else:
        od_cols.append(None)

records = []
current_group = ""
for line in lines[2:]:
    row = next(csv.reader([line]))
    if len(row) < 3:
        continue
    if "Group" in (row[0] or ""):
        g = (row[0] or "").replace("Group", "").strip()
        if g:
            current_group = g
        continue
    team = (row[1] if len(row) > 1 else "").strip()
    if not team:
        continue
    if team == "ales":
        team = "Wales"
    probs = []
    for ck in od_cols:
        if ck and ck in col_map:
            idx = col_map[ck]
            val = row[idx] if idx < len(row) else ""
            probs.append(american_odds_to_implied_prob(val))
        else:
            probs.append(0.5)
    result_cell = (row[-1] if len(row) > 0 else "").strip()
    is_winner = 1 if "WINNER" in result_cell.upper() else 0
    names = ["odds_sep2020", "odds_jun2022", "odds_nov2022", "odds_game2", "odds_game3"]
    features = dict(zip(names[:len(probs)], probs))
    records.append({
        "group": current_group, "team": team, "record_id": f"{current_group}-{team}",
        "odds_sep2020": probs[0] if len(probs) > 0 else 0.5,
        "odds_jun2022": probs[1] if len(probs) > 1 else 0.5,
        "odds_nov2022": probs[2] if len(probs) > 2 else 0.5,
        "odds_game2": probs[3] if len(probs) > 3 else 0.5,
        "odds_game3": probs[4] if len(probs) > 4 else 0.5,
        "is_winner": is_winner, "features": features,
    })

payload = {
    "data_type": "group_odds",
    "task": "group_winner",
    "records": records,
    "feature_cols": ["odds_sep2020", "odds_jun2022", "odds_nov2022", "odds_game2", "odds_game3"],
}
content = json.dumps(payload, ensure_ascii=False, indent=2)

# 4. 保存并创建 data_file
save_cleaned_file(args, content)
'''
