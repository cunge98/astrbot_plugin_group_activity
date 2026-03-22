"""HTML 模板 — 精美视觉增强版"""

import random

# 随机 slogan
SLOGANS = [
    "让每条消息都有意义 ✨",
    "潜水一时爽，被踢火葬场 🔥",
    "活跃是一种态度 💪",
    "今天你发言了吗？👀",
    "沉默不是金，发言才是真 💬",
    "群里有你更精彩 🌟",
    "键盘敲起来，潜水不存在 ⌨️",
    "每一句话都是存在的证明 📝",
    "冒个泡，证明你还活着 🫧",
    "别让灰尘落满了你的头像 🧹",
]

def get_slogan():
    return random.choice(SLOGANS)

# 4 套主题配色
THEMES = {
    "清新蓝": {
        "hdr1": "#4facfe", "hdr2": "#00f2fe",
        "rank_hdr1": "#f093fb", "rank_hdr2": "#f5576c", "rank_hdr3": "#ff9a76",
        "warn_hdr1": "#f5576c", "warn_hdr2": "#ffa751",
        "weekly_hdr1": "#2d1b69", "weekly_hdr2": "#44236e", "weekly_hdr3": "#6b3fa0",
        "query_hdr1": "#a18cd1", "query_hdr2": "#fbc2eb",
        "help_hdr1": "#667eea", "help_hdr2": "#764ba2",
        "stat_hdr1": "#43e97b", "stat_hdr2": "#38f9d7",
        "trend_hdr1": "#4facfe", "trend_hdr2": "#00f2fe", "trend_hdr3": "#43e97b",
        "ok_hdr1": "#11998e", "ok_hdr2": "#38ef7d",
        "bg": "#fff", "text": "#333", "text2": "#555", "subtle": "#bcc5d0",
        "sec_bg": "#f8f9fb", "row_alt": "#fafcfe", "border": "#f0f2f5", "sec_border": "#eef0f4",
        "sec_text": "#9aa4b0", "ft_bg": "#f8f9fb",
    },
    "活力橙": {
        "hdr1": "#f7971e", "hdr2": "#ffd200",
        "rank_hdr1": "#ee0979", "rank_hdr2": "#ff6a00", "rank_hdr3": "#ffd200",
        "warn_hdr1": "#d31027", "warn_hdr2": "#ea384d",
        "weekly_hdr1": "#7a2010", "weekly_hdr2": "#8b3000", "weekly_hdr3": "#b54500",
        "query_hdr1": "#fc5c7d", "query_hdr2": "#6a82fb",
        "help_hdr1": "#f7971e", "help_hdr2": "#ffd200",
        "stat_hdr1": "#56ab2f", "stat_hdr2": "#a8e063",
        "trend_hdr1": "#f7971e", "trend_hdr2": "#ffd200", "trend_hdr3": "#56ab2f",
        "ok_hdr1": "#56ab2f", "ok_hdr2": "#a8e063",
        "bg": "#fff", "text": "#333", "text2": "#555", "subtle": "#bcc5d0",
        "sec_bg": "#fef9f0", "row_alt": "#fefcf7", "border": "#f5ede0", "sec_border": "#f0e8d8",
        "sec_text": "#b09070", "ft_bg": "#fef9f0",
    },
    "优雅紫": {
        "hdr1": "#6a11cb", "hdr2": "#2575fc",
        "rank_hdr1": "#cc2b5e", "rank_hdr2": "#753a88", "rank_hdr3": "#2575fc",
        "warn_hdr1": "#c31432", "warn_hdr2": "#240b36",
        "weekly_hdr1": "#1a0533", "weekly_hdr2": "#2d0a4e", "weekly_hdr3": "#4a1680",
        "query_hdr1": "#8e2de2", "query_hdr2": "#4a00e0",
        "help_hdr1": "#6a11cb", "help_hdr2": "#2575fc",
        "stat_hdr1": "#200122", "stat_hdr2": "#6f0000",
        "trend_hdr1": "#6a11cb", "trend_hdr2": "#2575fc", "trend_hdr3": "#00d2ff",
        "ok_hdr1": "#11998e", "ok_hdr2": "#38ef7d",
        "bg": "#faf8ff", "text": "#2a2040", "text2": "#5a4f70", "subtle": "#b0a8c4",
        "sec_bg": "#f4f0fa", "row_alt": "#f8f5fd", "border": "#eae4f4", "sec_border": "#e0d8ef",
        "sec_text": "#9088a8", "ft_bg": "#f4f0fa",
    },
    "暗夜模式": {
        "hdr1": "#0f2027", "hdr2": "#2c5364",
        "rank_hdr1": "#1a1a2e", "rank_hdr2": "#16213e", "rank_hdr3": "#0f3460",
        "warn_hdr1": "#4a0000", "warn_hdr2": "#8e0000",
        "weekly_hdr1": "#0f2027", "weekly_hdr2": "#203a43", "weekly_hdr3": "#2c5364",
        "query_hdr1": "#1a1a2e", "query_hdr2": "#16213e",
        "help_hdr1": "#0f2027", "help_hdr2": "#2c5364",
        "stat_hdr1": "#0f2027", "stat_hdr2": "#203a43",
        "trend_hdr1": "#0f2027", "trend_hdr2": "#203a43", "trend_hdr3": "#2c5364",
        "ok_hdr1": "#0d4030", "ok_hdr2": "#1a6040",
        "bg": "#1a1a2e", "text": "#e0e0e0", "text2": "#a0a0b0", "subtle": "#606080",
        "sec_bg": "#16213e", "row_alt": "#1e2a45", "border": "#2a2a4e", "sec_border": "#252550",
        "sec_text": "#7080a0", "ft_bg": "#16213e",
    },
}


def _css(theme_name="清新蓝"):
    t = THEMES.get(theme_name, THEMES["清新蓝"])
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{margin:0;padding:0;font-family:'Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif;background:{t['bg']};-webkit-font-smoothing:antialiased}}
body{{display:flex;flex-direction:column;min-height:100vh}}
.container{{width:100%;flex:1;display:flex;flex-direction:column}}
.content{{flex:0 0 auto}}
.spacer{{flex:1 1 auto;background:linear-gradient(180deg,{t['bg']} 0%,{t['ft_bg']} 100%)}}
/* ==== 头部 ==== */
.hdr{{padding:32px 28px 28px;color:#fff;position:relative;overflow:hidden;min-height:160px}}
.hdr h1{{font-size:24px;font-weight:900;margin-bottom:5px;text-shadow:0 2px 4px rgba(0,0,0,.18);position:relative;z-index:2}}
.hdr .sub{{font-size:14px;opacity:.85;position:relative;z-index:2}}
.hdr .meta{{font-size:11px;opacity:.7;position:relative;z-index:2;margin-top:8px;display:flex;gap:12px;flex-wrap:wrap}}
.hdr .slogan{{font-size:11px;opacity:.6;position:relative;z-index:2;margin-top:4px;font-style:italic}}
.hdr .anime-bg{{position:absolute;right:0;top:0;height:100%;width:75%;object-fit:cover;object-position:center top;opacity:.9;z-index:1;pointer-events:none;mask-image:linear-gradient(to right,transparent 0%,rgba(0,0,0,.4) 8%,rgba(0,0,0,1) 100%);-webkit-mask-image:linear-gradient(to right,transparent 0%,rgba(0,0,0,.4) 8%,rgba(0,0,0,1) 100%)}}
.hdr-fade{{position:absolute;bottom:0;left:0;width:100%;height:40px;background:linear-gradient(to bottom,transparent,#fff);z-index:2;pointer-events:none}}
.hdr::after{{content:'';position:absolute;top:-40px;right:-40px;width:180px;height:180px;border-radius:50%;background:rgba(255,255,255,.1)}}
.hdr::before{{content:'';position:absolute;bottom:10px;left:20px;width:60px;height:60px;border-radius:50%;background:rgba(255,255,255,.06)}}
/* ==== 通用行 ==== */
.sec{{font-size:12px;font-weight:700;color:{t['sec_text']};letter-spacing:1.5px;padding:16px 28px 9px;background:{t['sec_bg']};border-bottom:1px solid {t['sec_border']}}}
.r{{display:flex;justify-content:space-between;align-items:center;padding:14px 28px;border-bottom:1px solid {t['border']};font-size:15px;color:{t['text']}}}
.r:last-child{{border-bottom:none}}
.r .l{{color:{t['text2']}}}
.r .v{{font-weight:600;color:{t['text']};text-align:right;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.t{{display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600}}
.tg{{background:#e8f5e9;color:#2e7d32}}.tr{{background:#ffeef0;color:#d32f2f}}
.ty{{background:#fff8e1;color:#e65100}}.tb{{background:#e3f2fd;color:#1565c0}}
/* ==== 表格 ==== */
table{{width:100%;border-collapse:collapse;font-size:15px}}
th{{background:{t['sec_bg']};color:{t['sec_text']};font-weight:700;text-align:left;padding:12px 18px;font-size:13px;border-bottom:2px solid {t['sec_border']}}}
td{{padding:14px 18px;border-bottom:1px solid {t['border']};color:{t['text']};vertical-align:middle}}
td.nick{{max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
tr:nth-child(even){{background:{t['row_alt']}}}
/* 前三高亮 */
tr.top1{{background:linear-gradient(90deg,#fffdf0,#fff8e1)}}
tr.top2{{background:linear-gradient(90deg,#f8f8fa,#f0f0f5)}}
tr.top3{{background:linear-gradient(90deg,#fdf8f4,#f8efe8)}}
/* ==== 头像 ==== */
.avatar{{width:36px;height:36px;border-radius:50%;object-fit:cover;vertical-align:middle;margin-right:10px;border:2px solid {t['border']};background:{t['sec_bg']}}}
/* ==== 奖牌 ==== */
.medal{{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:50%;font-weight:900;font-size:14px}}
.m1{{background:linear-gradient(145deg,#FFD700,#F0A000);color:#fff;box-shadow:0 2px 6px rgba(255,165,0,.4)}}
.m2{{background:linear-gradient(145deg,#D8D8D8,#9E9E9E);color:#fff;box-shadow:0 2px 5px rgba(150,150,150,.3)}}
.m3{{background:linear-gradient(145deg,#E8C896,#A07040);color:#fff;box-shadow:0 2px 5px rgba(160,112,64,.3)}}
.mn{{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border-radius:10px;font-weight:700;font-size:14px;color:{t['subtle']};background:{t['sec_bg']}}}
/* ==== 火焰徽章 ==== */
.fire-badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:700}}
.fire-1{{background:#fff3e0;color:#e65100}}
.fire-2{{background:#fbe9e7;color:#d84315}}
.fire-3{{background:#fce4ec;color:#c62828}}
/* ==== 圆环图 ==== */
.donut-wrap{{display:flex;align-items:center;justify-content:center;gap:20px;padding:20px 28px}}
.donut{{width:120px;height:120px;border-radius:50%;position:relative}}
.donut-label{{text-align:center;font-size:11px;color:{t['text2']};line-height:1.5}}
.donut-center{{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:20px;font-weight:900;color:{t['text']}}}
.legend{{font-size:12px;color:{t['text2']};line-height:2}}
.legend-dot{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:middle}}
/* ==== 进度条 ==== */
.pw{{background:{t['sec_bg']};border-radius:6px;height:12px;overflow:hidden;margin:6px 0}}
.pf{{height:100%;border-radius:6px}}
/* ==== 长文本 ==== */
.lt{{padding:22px 28px;font-size:15px;line-height:1.85;color:{t['text']};white-space:pre-wrap;word-break:break-word}}
.mb{{padding:16px 28px;font-size:14px;color:{t['text2']};background:{t['sec_bg']}}}
/* ==== 品牌底栏 ==== */
.brand{{flex:0 0 auto;display:flex;align-items:center;justify-content:center;gap:8px;padding:14px 28px;background:{t['ft_bg']};border-top:1px solid {t['sec_border']};font-size:11px;color:{t['subtle']}}}
.brand img{{width:16px;height:16px;border-radius:4px}}
/* ==== AI 评语 ==== */
.ai-comment{{padding:14px 28px;font-size:13px;color:{t['text2']};font-style:italic;border-top:1px dashed {t['border']};background:linear-gradient(90deg,{t['sec_bg']},{t['bg']})}}
/* ==== 周报卡片网格 ==== */
.metrics{{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:20px 28px}}
.metric-card{{background:{t['sec_bg']};border-radius:12px;padding:16px;text-align:center}}
.metric-val{{font-size:28px;font-weight:900;color:{t['text']};line-height:1.2}}
.metric-label{{font-size:11px;color:{t['text2']};margin-top:4px}}
.metric-change{{font-size:12px;font-weight:600;margin-top:6px}}
.metric-up{{color:#2e7d32}}
.metric-down{{color:#c62828}}
.metric-flat{{color:{t['subtle']}}}
/* 周报迷你柱状图 */
.mini-bars{{display:flex;align-items:flex-end;gap:6px;height:80px;padding:0 28px}}
.mini-col{{flex:1;display:flex;flex-direction:column;align-items:center}}
.mini-bar{{width:100%;border-radius:4px 4px 0 0;min-height:3px;background:linear-gradient(180deg,{t['hdr1']},{t['hdr2']})}}
.mini-val{{font-size:9px;color:{t['text2']};font-weight:600;margin-bottom:2px}}
.mini-label{{font-size:9px;color:{t['subtle']};margin-top:4px}}
/* 周报排名行 */
.rank-row{{display:flex;align-items:center;gap:12px;padding:12px 28px;border-bottom:1px solid {t['border']}}}
.rank-row:last-child{{border-bottom:none}}
.rank-num{{font-size:18px;font-weight:900;width:28px;text-align:center}}
.rank-avatar{{width:40px;height:40px;border-radius:50%;object-fit:cover;border:2px solid {t['border']}}}
.rank-info{{flex:1}}
.rank-name{{font-size:14px;font-weight:700;color:{t['text']}}}
.rank-detail{{font-size:11px;color:{t['text2']};margin-top:2px}}
/* AI 穿插短评 */
.ai-blurb{{padding:10px 28px;font-size:13px;color:{t['text2']};font-style:italic;background:{t['sec_bg']};border-left:3px solid {t['hdr1']}}}
/* ==== 周报领奖台 ==== */
.podium{{display:flex;justify-content:center;align-items:flex-end;gap:10px;padding:20px 16px 10px}}
.podium-item{{display:flex;flex-direction:column;align-items:center;flex:1;max-width:140px}}
.podium-avatar{{border-radius:50%;object-fit:cover;border:3px solid {t['border']};background:{t['sec_bg']}}}
.podium-1 .podium-avatar{{width:72px;height:72px;border-color:#FFD700;box-shadow:0 0 12px rgba(255,215,0,.5)}}
.podium-2 .podium-avatar{{width:56px;height:56px;border-color:#C0C0C0}}
.podium-3 .podium-avatar{{width:56px;height:56px;border-color:#CD7F32}}
.podium-medal{{font-size:20px;margin-top:4px}}
.podium-name{{font-size:13px;font-weight:700;color:{t['text']};margin-top:6px;text-align:center;max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.podium-stat{{font-size:11px;color:{t['text2']};margin-top:2px;text-align:center}}
.podium-bar{{width:100%;border-radius:8px 8px 0 0;margin-top:8px;display:flex;align-items:flex-end;justify-content:center;color:#fff;font-weight:900;font-size:16px;padding-bottom:6px}}
.podium-1 .podium-bar{{height:80px;background:linear-gradient(180deg,#FFD700,#F0A000)}}
.podium-2 .podium-bar{{height:56px;background:linear-gradient(180deg,#D8D8D8,#9E9E9E)}}
.podium-3 .podium-bar{{height:40px;background:linear-gradient(180deg,#E8C896,#A07040)}}
/* ==== 周报通缉令 ==== */
.wanted{{padding:12px 28px}}
.wanted-item{{display:flex;align-items:center;gap:10px;padding:8px 14px;margin-bottom:6px;border-radius:8px;background:{t['sec_bg']};border-left:3px solid #ef5350}}
.wanted-item:last-child{{margin-bottom:0}}
.wanted-idx{{font-size:14px;font-weight:900;color:#c62828;min-width:20px}}
.wanted-ava{{width:28px;height:28px;border-radius:50%;object-fit:cover;border:1px solid #ffcdd2}}
.wanted-name{{font-size:13px;font-weight:600;color:{t['text']}}}
.wanted-days{{font-size:12px;color:#c62828;font-weight:700;margin-left:auto}}
</style>
</head>
<body>
<div class="container">
"""

# 二次元背景图（所有页面共用）
_ANIME = '<img class="anime-bg" src="https://img.paulzzh.com/touhou/random" onerror="this.style.display=\'none\'"><div class="hdr-fade"></div>'

# 头部 meta - 完整版（含人数，用于排行榜和周报）
_META_FULL = '<div class="meta"><span>{{ group_name }}</span><span>共 {{ member_count }} 人</span><span>{{ now }}</span></div><div class="slogan">{{ slogan }}</div>'

# 头部 meta - 精简版（不含人数）
_META = '<div class="meta"><span>{{ now }}</span></div><div class="slogan">{{ slogan }}</div>'

# 品牌底栏（Jinja2 模板）
_BRAND = '<div class="brand"><span>群活跃检测 v2.1</span><span>·</span><span>{{ now }}</span></div>'

_TAIL = """
</div>
</body>
</html>"""


# ====== 帮助 ======
def HELP(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['help_hdr1']},{t['help_hdr2']})">
  {_ANIME}
  <h1>📋 群活跃检测 · 指令帮助</h1><div class="sub">AI 增强版 v2.1</div>
  {_META}
</div>
""" + """
<div class="sec">👥 所有人可用</div>
<div class="r"><span class="l">/活跃排行</span><span class="v">查看群活跃排行榜</span></div>
<div class="r"><span class="l">/活跃查询</span><span class="v">查询自己的活跃信息</span></div>
<div class="r"><span class="l">/活跃趋势</span><span class="v">近14天群活跃趋势图</span></div>
<div class="r"><span class="l">/活跃帮助</span><span class="v">显示本帮助页面</span></div>
<div class="sec">🔑 管理员专用</div>
<div class="r"><span class="l">/活跃检测</span><span class="v">查看检测状态和配置</span></div>
<div class="r"><span class="l">/活跃统计</span><span class="v">群整体数据摘要</span></div>
<div class="r"><span class="l">/不活跃列表</span><span class="v">查看不活跃成员列表</span></div>
<div class="r"><span class="l">/手动检测</span><span class="v">立即执行一次检测</span></div>
<div class="r"><span class="l">/初始化活跃数据</span><span class="v">初始化群成员数据</span></div>
<div class="r"><span class="l">/清除警告 [QQ号]</span><span class="v">清除警告状态</span></div>
<div class="r"><span class="l">/群周报</span><span class="v">AI 生成群活跃周报</span></div>
{% if ai %}
<div class="sec">🤖 AI 功能</div>
<div class="r"><span class="l">@Bot + 理由</span><span class="v">被警告后向AI申诉求生</span></div>
<div class="r"><span class="l">自然语言提问</span><span class="v">问Bot群里谁最活跃等</span></div>
{% endif %}
""" + _BRAND + _TAIL


# ====== 运行状态 ======
def STATUS(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['hdr1']},{t['hdr2']})">
  {_ANIME}
  <h1>⚙️ 群活跃检测 · 运行状态</h1><div class="sub">v2.1 AI 增强版</div>
  {_META}
</div>
""" + f"""
<div class="sec">基础配置</div>
<div class="r"><span class="l">全局开关</span><span class="t {{{{ 'tg' if enabled else 'tr' }}}}">{{{{ '已开启' if enabled else '已关闭' }}}}</span></div>
<div class="r"><span class="l">运行模式</span><span class="t tb">{{{{ mode }}}}</span></div>
<div class="r"><span class="l">白名单群数</span><span class="v">{{{{ wl }}}} 个</span></div>
<div class="r"><span class="l">黑名单群数</span><span class="v">{{{{ bl }}}} 个</span></div>
<div class="r"><span class="l">不活跃阈值</span><span class="v">{{{{ days }}}} 天</span></div>
<div class="r"><span class="l">警告后踢出</span><span class="v">{{{{ hours }}}} 小时</span></div>
<div class="r"><span class="l">检测间隔</span><span class="v">{{{{ interval }}}} 分钟</span></div>
<div class="sec">AI 功能</div>
<div class="r"><span class="l">AI 增强</span><span class="t {{{{ 'tg' if ai else 'tr' }}}}">{{{{ '已开启' if ai else '未开启' }}}}</span></div>
<div class="r"><span class="l">AI 模型</span><span class="v">{{{{ provider or '默认' }}}}</span></div>
<div class="r"><span class="l">AI 人设</span><span class="v">{{{{ '自定义' if custom_prompt else style }}}}</span></div>
<div class="r"><span class="l">AI 申诉</span><span class="t {{{{ 'tg' if appeal else 'tr' }}}}">{{{{ '已开启' if appeal else '未开启' }}}}</span></div>
<div class="r"><span class="l">自动周报</span><span class="t {{{{ 'tg' if auto_weekly else 'tr' }}}}">{{{{ auto_weekly_day + ' ' + auto_weekly_time if auto_weekly else '未开启' }}}}</span></div>
<div class="sec">统计</div>
<div class="r"><span class="l">追踪成员总数</span><span class="v">{{{{ tt }}}}</span></div>
<div class="r"><span class="l">当前被警告</span><span class="v" style="color:{{{{ '#c62828' if tw>0 else '#2e7d32' }}}}">{{{{ tw }}}}</span></div>
{{% if ai_comment %}}<div class="ai-comment">🤖 {{{{ ai_comment }}}}</div>{{% endif %}}
""" + _BRAND + _TAIL


# ====== 排行榜 ======
def RANK(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['rank_hdr1']},{t['rank_hdr2']},{t['rank_hdr3']})">
  {_ANIME}
  <h1>🏆 群活跃排行榜</h1><div class="sub">共追踪 {{{{ total }}}} 名成员</div>
  {_META_FULL}
</div>
""" + """
<table>
  <tr><th style="width:50px">#</th><th>成员</th><th style="width:52px">🔥连续</th><th style="width:76px">最后发言</th><th style="width:52px">状态</th></tr>
  {% for m in ms %}
  <tr class="{{ 'top1' if m.i==1 else ('top2' if m.i==2 else ('top3' if m.i==3 else '')) }}">
    <td>{% if m.i==1 %}<span class="medal m1">1</span>{% elif m.i==2 %}<span class="medal m2">2</span>{% elif m.i==3 %}<span class="medal m3">3</span>{% else %}<span class="mn">{{ m.i }}</span>{% endif %}</td>
    <td class="nick"><img class="avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{ m.qq }}&s=40" onerror="this.style.display='none'">{{ m.n }}</td>
    <td style="color:#e65100;font-weight:700;font-size:13px;text-align:center">{% if m.sk>=7 %}🔥🔥🔥{% elif m.sk>=3 %}🔥🔥{% elif m.sk>=1 %}🔥{% endif %}{{ m.sk }}天</td>
    <td style="font-size:12px;opacity:.7">{{ m.t }}</td>
    <td>{% if m.w %}<span class="t ty">已警告</span>{% else %}<span class="t tg">正常</span>{% endif %}</td>
  </tr>
  {% endfor %}
</table>
""" + _BRAND + _TAIL


# ====== 个人查询 ======
def QUERY(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['query_hdr1']},{t['query_hdr2']})">
  {_ANIME}
  <h1>{{{{ nick }}}}</h1><div class="sub">个人活跃信息</div>
  {_META}
</div>
""" + f"""
<div class="r"><span class="l">连续活跃</span><span class="fire-badge {{{{ 'fire-3' if streak>=7 else ('fire-2' if streak>=3 else 'fire-1') }}}}">{{{{ '🔥🔥🔥' if streak>=7 else ('🔥🔥' if streak>=3 else '🔥') }}}} {{{{ streak }}}} 天</span></div>
<div class="r"><span class="l">最后发言</span><span class="v">{{{{ ts }}}}</span></div>
<div class="r"><span class="l">不活跃天数</span><span class="v">{{{{ iday }}}} 天</span></div>
<div class="r"><span class="l">安全状态</span><span class="t {{{{ 'tg' if safe else 'tr' }}}}">{{{{ '安全' if safe else '已超阈值' }}}}</span></div>
<div class="r"><span class="l">已被警告</span>{{% if wa %}}<span class="t ty">是（剩余 {{{{ rem }}}}）</span>{{% else %}}<span class="t tg">否</span>{{% endif %}}</div>
<div class="r"><span class="l">检测阈值</span><span class="v">{{{{ th }}}} 天</span></div>
<div style="padding:14px 28px">
  <div style="font-size:12px;color:{t['subtle']};margin-bottom:5px">活跃度 · 距阈值 {{{{ left }}}} 天</div>
  <div class="pw"><div class="pf" style="width:{{{{ prog }}}}%;background:linear-gradient(90deg,{{{{ cs }}}},{{{{ ce }}}})"></div></div>
  <div style="text-align:right;font-size:11px;color:{t['subtle']};margin-top:3px">{{{{ prog }}}}%</div>
</div>
""" + _BRAND + _TAIL


# ====== 不活跃列表 ======
def INACTIVE(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['warn_hdr1']},{t['warn_hdr2']})">
  {_ANIME}
  <h1>⚠️ 不活跃成员列表</h1><div class="sub">超过 {{{{ th }}}} 天未发言 · 共 {{{{ total }}}} 人</div>
  {_META}
</div>
""" + """
<table>
  <tr><th>昵称</th><th style="width:80px">未发言</th><th style="width:56px">状态</th></tr>
  {% for m in ms %}
  <tr>
    <td class="nick">{{ m.n }}</td>
    <td style="color:#c62828;font-weight:700">{{ m.d }} 天</td>
    <td>{% if m.w %}<span class="t ty">已警告</span>{% else %}<span class="t tb">待检测</span>{% endif %}</td>
  </tr>
  {% endfor %}
</table>
""" + _BRAND + _TAIL


# ====== 全员活跃 ======
def ALL_OK(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['ok_hdr1']},{t['ok_hdr2']})">
  {_ANIME}
  <h1>🎉 全员活跃</h1><div class="sub">群氛围很活跃</div>
  {_META}
</div>
""" + """
<div class="mb" style="text-align:center;padding:28px;font-size:16px;color:#2e7d32">
  当前群没有超过 {{ th }} 天未发言的成员！
</div>
""" + _BRAND + _TAIL


# ====== 周报 ======
def WEEKLY(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['weekly_hdr1']},{t['weekly_hdr2']},{t['weekly_hdr3']});min-height:160px">
  {_ANIME}
  <h1>📰 群活跃周报</h1><div class="sub">{{{{ date }}}} · AI 人设: {{{{ style }}}}</div>
  {_META_FULL}
</div>
<div class="sec">📊 本周数据概览</div>
<div class="metrics">
  <div class="metric-card">
    <div class="metric-val">{{{{ this_week_msgs }}}}</div>
    <div class="metric-label">本周消息数</div>
    <div class="metric-change {{{{ 'metric-up' if this_week_msgs > last_week_msgs else ('metric-down' if this_week_msgs < last_week_msgs else 'metric-flat') }}}}">
      {{{{ '↑' if this_week_msgs > last_week_msgs else ('↓' if this_week_msgs < last_week_msgs else '→') }}}} 上周 {{{{ last_week_msgs }}}} 条
    </div>
  </div>
  <div class="metric-card">
    <div class="metric-val">{{{{ active_count }}}}</div>
    <div class="metric-label">本周活跃人数</div>
    <div class="metric-change metric-flat">共 {{{{ total }}}} 人</div>
  </div>
  <div class="metric-card">
    <div class="metric-val" style="color:#e65100">{{{{ warned }}}}</div>
    <div class="metric-label">当前被警告</div>
  </div>
  <div class="metric-card">
    <div class="metric-val" style="color:{{{{ '#2e7d32' if change_pct >= 0 else '#c62828' }}}}">{{{{ change_pct }}}}%</div>
    <div class="metric-label">周环比变化</div>
    <div class="metric-change {{{{ 'metric-up' if change_pct > 0 else ('metric-down' if change_pct < 0 else 'metric-flat') }}}}">
      {{{{ '活跃度上升' if change_pct > 0 else ('活跃度下降' if change_pct < 0 else '持平') }}}}
    </div>
  </div>
</div>
{{% if ai1 %}}<div class="ai-blurb">🤖 {{{{ ai1 }}}}</div>{{% endif %}}
<div class="sec">📈 近7天消息量</div>
<div style="padding:16px 0 8px">
  <div class="mini-bars">
    {{% for d in chart %}}
    <div class="mini-col">
      <div class="mini-val">{{{{ d.v }}}}</div>
      <div class="mini-bar" style="height:{{{{ d.pct }}}}%"></div>
      <div class="mini-label">{{{{ d.label }}}}</div>
    </div>
    {{% endfor %}}
  </div>
</div>
{{% if ai2 %}}<div class="ai-blurb">🤖 {{{{ ai2 }}}}</div>{{% endif %}}
<div class="sec">🏆 本周最活跃 Top3</div>
<div class="podium">
  {{% if top3|length >= 2 %}}
  <div class="podium-item podium-2">
    <img class="podium-avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ top3[1].qq }}}}&s=100" onerror="this.style.display='none'">
    <div class="podium-medal">🥈</div>
    <div class="podium-name">{{{{ top3[1].n }}}}</div>
    <div class="podium-stat">🔥{{{{ top3[1].sk }}}}天 · {{{{ top3[1].t }}}}</div>
    <div class="podium-bar">2</div>
  </div>
  {{% endif %}}
  {{% if top3|length >= 1 %}}
  <div class="podium-item podium-1">
    <img class="podium-avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ top3[0].qq }}}}&s=100" onerror="this.style.display='none'">
    <div class="podium-medal">🥇</div>
    <div class="podium-name">{{{{ top3[0].n }}}}</div>
    <div class="podium-stat">🔥{{{{ top3[0].sk }}}}天 · {{{{ top3[0].t }}}}</div>
    <div class="podium-bar">1</div>
  </div>
  {{% endif %}}
  {{% if top3|length >= 3 %}}
  <div class="podium-item podium-3">
    <img class="podium-avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ top3[2].qq }}}}&s=100" onerror="this.style.display='none'">
    <div class="podium-medal">🥉</div>
    <div class="podium-name">{{{{ top3[2].n }}}}</div>
    <div class="podium-stat">🔥{{{{ top3[2].sk }}}}天 · {{{{ top3[2].t }}}}</div>
    <div class="podium-bar">3</div>
  </div>
  {{% endif %}}
</div>
{{% if ai3 %}}<div class="ai-blurb">🤖 {{{{ ai3 }}}}</div>{{% endif %}}
<div class="sec">🚨 本周潜水通缉令</div>
<div class="wanted">
  {{% for m in bot3 %}}
  <div class="wanted-item">
    <div class="wanted-idx">{{{{ loop.index }}}}</div>
    <img class="wanted-ava" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ m.qq }}}}&s=40" onerror="this.style.display='none'">
    <div class="wanted-name">{{{{ m.n }}}}</div>
    <div class="wanted-days">{{{{ m.days }}}}天未发言</div>
  </div>
  {{% endfor %}}
</div>
{{% if not bot3 %}}
<div style="padding:16px 28px;color:#2e7d32;font-size:14px">🎉 本周没有严重潜水的成员！</div>
{{% endif %}}
{{% if ai4 %}}<div class="ai-blurb">🤖 {{{{ ai4 }}}}</div>{{% endif %}}
""" + _BRAND + _TAIL


# ====== 通用结果 ======
def RESULT(th):
    return _css(th) + """
<div class="hdr" style="background:linear-gradient(135deg,{{ c1 }},{{ c2 }})">
  """ + _ANIME + """
  <h1>{{ title }}</h1>{% if sub %}<div class="sub">{{ sub }}</div>{% endif %}
  """ + _META + """
</div>
""" + """
{% for kv in rows %}
<div class="r"><span class="l">{{ kv.k }}</span><span class="v">{{ kv.v }}</span></div>
{% endfor %}
{% if msg %}<div class="mb">{{ msg }}</div>{% endif %}
""" + _BRAND + _TAIL


# ====== 活跃统计 ======
def STATS(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<div class="hdr" style="background:linear-gradient(135deg,{t['stat_hdr1']},{t['stat_hdr2']})">
  {_ANIME}
  <h1>📊 群活跃统计</h1><div class="sub">群整体数据摘要</div>
  {_META}
</div>
""" + f"""
<div class="sec">基本信息</div>
<div class="r"><span class="l">追踪成员数</span><span class="v">{{{{ total }}}}</span></div>
<div class="r"><span class="l">今日发言人数</span><span class="v" style="color:#2e7d32">{{{{ today_active }}}}</span></div>
<div class="r"><span class="l">近7天活跃人数</span><span class="v">{{{{ week_active }}}}</span></div>
<div class="r"><span class="l">近7天沉默人数</span><span class="v" style="color:#c62828">{{{{ week_silent }}}}</span></div>
<div class="sec">活跃度分布</div>
<div class="donut-wrap">
  <div class="donut" style="background:conic-gradient(#4caf50 0% {{{{ p1 }}}}%,#8bc34a {{{{ p1 }}}}% {{{{ p2 }}}}%,#ffeb3b {{{{ p2 }}}}% {{{{ p3 }}}}%,#ff9800 {{{{ p3 }}}}% {{{{ p4 }}}}%,#f44336 {{{{ p4 }}}}% 100%)">
    <div class="donut-center" style="width:70px;height:70px;background:{t['bg']};border-radius:50%"></div>
  </div>
  <div class="legend">
    <div><span class="legend-dot" style="background:#4caf50"></span>1天内 {{{{ d1 }}}}人</div>
    <div><span class="legend-dot" style="background:#8bc34a"></span>1~3天 {{{{ d3 }}}}人</div>
    <div><span class="legend-dot" style="background:#ffeb3b"></span>3~7天 {{{{ d7 }}}}人</div>
    <div><span class="legend-dot" style="background:#ff9800"></span>7~30天 {{{{ d30 }}}}人</div>
    <div><span class="legend-dot" style="background:#f44336"></span>30天+ {{{{ d30p }}}}人</div>
  </div>
</div>
<div class="sec">最活跃 Top3</div>
{{% for m in top3 %}}
<div class="rank-row">
  <div class="rank-num" style="color:{{{{ '#F0A000' if loop.index==1 else ('#9E9E9E' if loop.index==2 else '#A07040') }}}}">{{{{ loop.index }}}}</div>
  <img class="rank-avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ m.qq }}}}&s=40" onerror="this.style.display='none'">
  <div class="rank-info">
    <div class="rank-name">{{{{ m.n }}}}</div>
    <div class="rank-detail">🔥 连续活跃 {{{{ m.sk }}}} 天 · {{{{ m.t }}}}</div>
  </div>
</div>
{{% endfor %}}
<div class="sec">最沉默 Top3</div>
{{% for m in bot3 %}}
<div class="rank-row">
  <div class="rank-num" style="color:#c62828">{{{{ loop.index }}}}</div>
  <img class="rank-avatar" src="https://q1.qlogo.cn/g?b=qq&nk={{{{ m.qq }}}}&s=40" onerror="this.style.display='none'">
  <div class="rank-info">
    <div class="rank-name">{{{{ m.n }}}}</div>
    <div class="rank-detail">已 {{{{ m.days }}}} 天未发言</div>
  </div>
</div>
{{% endfor %}}
<div class="r"><span class="l">当前被警告</span><span class="v" style="color:{{{{ '#c62828' if warned>0 else '#2e7d32' }}}}">{{{{ warned }}}}</span></div>
""" + _BRAND + _TAIL


# ====== 趋势图 ======
def TREND(th):
    t = THEMES.get(th, THEMES["清新蓝"])
    return _css(th) + f"""
<style>
.chart{{padding:20px 28px 10px}}
.chart-title{{font-size:13px;color:{t['text2']};margin-bottom:12px}}
.bars{{display:flex;align-items:flex-end;gap:5px;height:160px}}
.bar-col{{flex:1;display:flex;flex-direction:column;align-items:center}}
.bar{{width:100%;border-radius:5px 5px 0 0;min-height:3px}}
.bar-label{{font-size:10px;color:{t['subtle']};margin-top:6px;white-space:nowrap}}
.bar-val{{font-size:10px;color:{t['text2']};font-weight:600;margin-bottom:3px}}
</style>
<div class="hdr" style="background:linear-gradient(135deg,{t['trend_hdr1']},{t['trend_hdr2']},{t['trend_hdr3']})">
  {_ANIME}
  <h1>📈 群活跃趋势</h1><div class="sub">近 {{{{ days }}}} 天发言统计</div>
  {_META}
</div>
""" + """
<div class="chart">
  <div class="chart-title">每日群消息数量</div>
  <div class="bars">
    {% for d in data %}
    <div class="bar-col">
      <div class="bar-val">{{ d.v }}</div>
      <div class="bar" style="height:{{ d.pct }}%;background:linear-gradient(180deg,{{ d.color }},{{ d.color2 }})"></div>
      <div class="bar-label">{{ d.label }}</div>
    </div>
    {% endfor %}
  </div>
</div>
<div class="sec">数据概览</div>
<div class="r"><span class="l">日均消息数</span><span class="v">{{ avg }}</span></div>
<div class="r"><span class="l">最高峰</span><span class="v">{{ peak_day }} ({{ peak_val }}条)</span></div>
<div class="r"><span class="l">最低谷</span><span class="v">{{ low_day }} ({{ low_val }}条)</span></div>
<div class="r"><span class="l">总消息数</span><span class="v">{{ total_msgs }}</span></div>
""" + _BRAND + _TAIL
