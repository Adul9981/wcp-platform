"""中英对照 + 标题翻译。

目标（用户优化要求 #2 #6）：所有英文队名/球员名/术语统一替换成中文，标题永远中文。
对照表同步维护在知识库 2_数据库/中英对照表.md。
翻译策略：先替换长短语模板，再替换队名/球员名（均按长度降序，避免部分匹配）。
"""
import re

# ---- 国家队（含所有变体写法 → 统一中文）----
TEAMS = {
    "Algeria": "阿尔及利亚", "Argentina": "阿根廷", "Australia": "澳大利亚",
    "Austria": "奥地利", "Belgium": "比利时",
    "Bosnia and Herzegovina": "波黑", "Bosnia-Herzegovina": "波黑", "Bosnia & Herzegovina": "波黑",
    "Brazil": "巴西", "Cabo Verde": "佛得角", "Cape Verde": "佛得角",
    "Canada": "加拿大", "Colombia": "哥伦比亚", "Croatia": "克罗地亚",
    "Curaçao": "库拉索", "Czechia": "捷克",
    "Côte d'Ivoire": "科特迪瓦", "Ivory Coast": "科特迪瓦",
    "DR Congo": "刚果（金）", "Ecuador": "厄瓜多尔", "Egypt": "埃及",
    "England": "英格兰", "France": "法国", "Germany": "德国", "Ghana": "加纳",
    "Haiti": "海地", "IR Iran": "伊朗", "Iran": "伊朗", "Iraq": "伊拉克",
    "Japan": "日本", "Jordan": "约旦",
    "Korea Republic": "韩国", "South Korea": "韩国",
    "Mexico": "墨西哥", "Morocco": "摩洛哥", "Netherlands": "荷兰",
    "New Zealand": "新西兰", "Norway": "挪威", "Panama": "巴拿马",
    "Paraguay": "巴拉圭", "Portugal": "葡萄牙", "Qatar": "卡塔尔",
    "Saudi Arabia": "沙特阿拉伯", "Scotland": "苏格兰", "Senegal": "塞内加尔",
    "South Africa": "南非", "Spain": "西班牙", "Sweden": "瑞典",
    "Switzerland": "瑞士", "Tunisia": "突尼斯", "Türkiye": "土耳其", "Turkiye": "土耳其",
    "United States": "美国", "USA": "美国", "Uruguay": "乌拉圭", "Uzbekistan": "乌兹别克斯坦",
}

# ---- 球员（H2H 盘口）----
PLAYERS = {
    "Messi": "梅西", "Ronaldo": "C罗", "Valverde": "巴尔韦德", "Fernandes": "B费",
    "Vitinha": "维蒂尼亚", "Pedri": "佩德里", "Dembele": "登贝莱", "Olise": "奥利塞",
    "Yamal": "亚马尔", "Mbappe": "姆巴佩", "Haaland": "哈兰德", "Alvarez": "阿尔瓦雷斯",
    "Salah": "萨拉赫", "Mane": "马内", "Neymar": "内马尔", "Vinicius Jr.": "维尼修斯",
    "Vinicius Jr": "维尼修斯",
}

# ---- 短语 / 模板（按更具体优先）----
PHRASES = {
    "World Cup Winner": "世界杯冠军",
    "World Cup:": "世界杯：",
    "World Cup": "世界杯",
    "Golden Boot Winner": "金靴奖得主", "Silver Boot Winner": "银靴奖得主",
    "Bronze Boot Winner": "铜靴奖得主", "Golden Boot": "金靴奖",
    "Golden Ball Winner": "金球奖得主", "Silver Ball Winner": "银球奖得主",
    "Bronze Ball Winner": "铜球奖得主", "Golden Glove Winner": "金手套奖得主",
    "Top Scorer": "最佳射手", "Top Goalscorer": "最佳射手",
    "Most Goal Contributions": "最多进球贡献", "Most Goals": "最多进球",
    "Most Assists": "最多助攻", "Most Clean Sheets": "最多零封",
    "Nation of Top Goalscorer": "最佳射手所属国家",
    "Nation To Reach Quarterfinals": "晋级八强的国家",
    "Nation To Reach Semifinals": "晋级四强的国家",
    "Nation to Reach Final": "晋级决赛的国家",
    "Nation To Reach Round of 16": "晋级16强的国家",
    "Team to advance to Knockout Stages": "晋级淘汰赛的球队",
    "Knockout Stage": "淘汰赛", "Stage of Elimination": "止步阶段",
    "Furthest Advancing Host Nation": "走得最远的东道主",
    "Furthest Advancing CAF Nation": "走得最远的非洲球队",
    "Furthest Advancing UEFA Nation": "走得最远的欧洲球队",
    "Furthest Advancing AFC Nation": "走得最远的亚洲球队",
    "Furthest Advancing": "走得最远的",
    "Worst-Placed UEFA Nation": "排名最低的欧洲球队",
    "Worst-Placed Host Nation": "排名最低的东道主",
    "Last Place": "垫底", "Second Place": "第二名", "First Place": "头名",
    "Highest-Scoring": "进球最多", "Highest Scoring": "进球最多",
    "Player to score": "进球球员", "Fair Play Award Winner": "公平竞赛奖得主",
    "Goalkeeper to Score": "门将进球", "Hat Trick": "帽子戏法",
    "Free Kick": "任意球", "Penalty": "点球",
    "Exact Score": "准确比分", "More Markets": "综合盘",
    "First Team to Score": "首支进球球队", "First to Score": "首支进球",
    "Both Teams to Score": "双方均进球", "Total Corners": "总角球数",
    "Halftime Result": "半场结果", "First Half": "上半场", "1st Half": "上半场",
    "Goal Contributions H2H": "进球贡献对决", "Goals H2H": "进球对决",
    "Stage of Elimination": "止步阶段",
    " vs. ": " 对 ", " vs ": " 对 ",
    "O/U": "大小球", "Draw": "平局", "Group": "小组",
    # 花边 / 纪录 / 问句类
    "Fastest Goal in a Final": "决赛最快进球", "Fastest Goal": "最快进球",
    "Largest Margin of Victory": "最大分差胜利",
    "Highest-Scoring Match": "进球最多的比赛", "Highest Scoring Match": "进球最多的比赛",
    "Single Match Yellow Cards": "单场黄牌数", "Total Tournament Goals": "赛事总进球数",
    "Most Player Goals": "球员最多进球", "Record Broken": "纪录被打破",
    "to Score a Free Kick": "任意球进球", "to Score 2+ Penalties": "打入2个以上点球",
    "to Score": "进球", "Goalkeeper to Score": "门将进球",
    "President Trump to Attend": "特朗普出席", "to Attend": "出席", "Trump": "特朗普",
    "Champions Photo": "冠军合影", "Opening Match": "揭幕战",
    "Worst-Placed CONMEBOL Nation": "排名最低的南美球队",
    "CONMEBOL Nation": "南美球队", "CONMEBOL": "南美", "Worst-Placed": "排名最低的",
    "Penalty Shoot": "点球大战", "Penalty Made or Missed": "点球罚中或罚失",
    "Scoreless Team": "零进球球队", "Winless Team": "不胜球队",
    "Unbeaten Champion": "不败夺冠", "to Cry": "哭泣",
    "Any Team to Score": "任意球队打入", "Any Player to Score": "任意球员打入",
    "Any Other Score": "其他比分", "Round of 16": "16强", "Quarterfinal": "八强",
    "Semifinal": "四强", "Final": "决赛", "Will ": "", "to Play in the": "参加",
    "Stage of Elimination": "止步阶段",
    # 大洲(含 Non-Host 组合，长串优先)
    "Non-Host CONCACAF Nation": "非东道主中北美球队", "Non-Host CONMEBOL Nation": "非东道主南美球队",
    "Non-Host": "非东道主",
    "CONCACAF Nation": "中北美球队", "CAF Nation": "非洲球队", "AFC Nation": "亚洲球队",
    "UEFA Nation": "欧洲球队", "Host Nation": "东道主",
    "CONCACAF": "中北美", "CONMEBOL": "南美", "CAF": "非洲", "UEFA": "欧洲", "AFC": "亚洲", "OFC": "大洋洲",
    # 通用词
    "Group Stage": "小组赛", "Knockout Phase": "淘汰赛阶段",
    "Highest-Scoring Team": "进球最多球队", "Team in Group": "球队（小组",
    "Nation": "国家", "Team": "球队", "Stage": "阶段",
    "Which continent will win the World Cup": "哪个大洲会夺冠", "continent": "大洲",
    "How many World Cup matches will": "会出席几场世界杯比赛——", "matches will": "",
    " in the World Cup": "", "play in the World Cup": "参加世界杯",
    " will ": " ", "attend": "出席", "How many": "多少",
    " in Group ": " 小组", " in ": " ",
    "?": "？",
}


def _replace_sorted(text, mapping):
    for k in sorted(mapping, key=len, reverse=True):
        if k in text:
            text = text.replace(k, mapping[k])
    return text


def translate(text: str) -> str:
    """英文标题/术语 → 中文。找不到的保留原文（不报错）。"""
    if not text:
        return text
    text = _replace_sorted(text, PHRASES)
    text = _replace_sorted(text, PLAYERS)
    text = _replace_sorted(text, TEAMS)
    return text


def team_zh(name: str) -> str:
    return TEAMS.get(name, name)
