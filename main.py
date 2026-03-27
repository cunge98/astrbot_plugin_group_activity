"""群成员活跃度检测插件（AI 增强版 v2.1）

Playwright 浏览器渲染高清图片 + LLM 大模型集成。
"""

import json, time, asyncio, random, datetime, base64
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger, AstrBotConfig
import astrbot.api.message_components as Comp

try:
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
except ImportError:
    AiocqhttpMessageEvent = None

from . import templates as T  # HELP STATUS RANK QUERY INACTIVE ALL_OK WEEKLY RESULT STATS TREND HEATMAP CHECKIN

try:
    from astrbot.core.utils.astrbot_path import get_astrbot_data_path
    DATA_DIR = Path(get_astrbot_data_path()) / "plugin_data" / "astrbot_plugin_group_activity"
except ImportError:
    DATA_DIR = Path("data") / "plugin_data" / "astrbot_plugin_group_activity"

# Playwright 高清截图 — 多策略降级
RENDER_STRATEGIES = [
    {"full_page": True, "type": "png", "scale": "device", "device_scale_factor_level": "ultra", "viewport_width": 540},
    {"full_page": True, "type": "jpeg", "quality": 100, "scale": "device", "device_scale_factor_level": "ultra", "viewport_width": 540},
    {"full_page": True, "type": "jpeg", "quality": 95, "scale": "device", "device_scale_factor_level": "high", "viewport_width": 540},
    {"full_page": True, "type": "jpeg", "quality": 80, "scale": "device", "viewport_width": 540},
]

AI_PERSONAS = {
    "傲娇萌妹": "你是一个傲娇的群管理萌妹，说话带点嘲讽但又可爱，用口语化中文，偶尔用颜文字。",
    "严苛群管": "你是严肃认真的群管理员，语气犀利直接，不留情面但有道理。",
    "毒舌段子手": "你是幽默毒舌的群管理员，喜欢网络梗和段子，损人但不伤人。",
    "古风仙人": "你是修真界仙人，半文言半白话，把群聊比作修仙门派，潜水=闭关。",
    "热血解说员": "你是热血体育解说员，把群活跃度当比赛来解说，充满激情夸张。",
}
FALLBACK = [
    "{nickname}，你已经 {days} 天没说话了！再不冒泡 {hours} 小时后就要被请出去啦~",
    "喂喂喂，{nickname}！潜水 {days} 天了？{hours} 小时内不发言就拜拜了！",
    "{nickname} 同学，沉默了 {days} 天。还有 {hours} 小时的机会，冒个泡吧！",
]


@register("astrbot_plugin_group_activity", "Dalimao", "AI 驱动的群成员活跃度检测与管理插件", "2.1.0")
class GroupActivityPlugin(Star):

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.data_file = DATA_DIR / "activity_data.json"
        self.activity_data = self._load()
        self._bot_client = None
        self._bot_self_id = None
        self._dirty = False           # 数据是否有未保存的变更
        self._last_save = 0           # 上次保存时间戳
        self._save_interval = 30      # 最小保存间隔（秒）
        self._wl_cache = None         # 白名单缓存
        self._bl_cache = None         # 黑名单缓存
        self._cache_time = 0          # 缓存刷新时间
        self._cache_ttl = 60          # 缓存有效期（秒）
        self._task = asyncio.create_task(self._loop())
        logger.info("群活跃检测插件 v2.1 已加载")

    # ==================== 数据 ====================

    def _load(self):
        try:
            if self.data_file.exists():
                return json.loads(self.data_file.read_text("utf-8"))
        except Exception as e: logger.error(f"加载数据失败: {e}")
        return {"groups": {}}

    def _save(self):
        """防抖保存：标记脏数据，间隔内最多写一次磁盘"""
        now = time.time()
        if now - self._last_save >= self._save_interval:
            self._force_save()
        else:
            self._dirty = True

    def _force_save(self):
        """立即写入磁盘"""
        try:
            self.data_file.write_text(json.dumps(self.activity_data, ensure_ascii=False, separators=(',', ':')), "utf-8")
            self._dirty = False
            self._last_save = time.time()
        except Exception as e:
            logger.error(f"保存数据失败: {e}")

    # ==================== 配置 ====================

    def _ls(self, k):
        v = self.config.get(k, [])
        return [str(g).strip() for g in v if str(g).strip()] if isinstance(v, list) else [g.strip() for g in str(v).split("\n") if g.strip()]

    def _wl(self):
        now = time.time()
        if self._wl_cache is None or now - self._cache_time > self._cache_ttl:
            self._wl_cache = self._ls("whitelist_groups")
            self._bl_cache = self._ls("blacklist_groups")
            self._cache_time = now
        return self._wl_cache

    def _bl(self):
        now = time.time()
        if self._bl_cache is None or now - self._cache_time > self._cache_ttl:
            self._wl()  # 触发缓存刷新
        return self._bl_cache

    def _mon(self, gid):
        if not self.config.get("enabled"): return False
        gid = str(gid)
        if gid in self._bl(): return False
        w = self._wl()
        return gid in w if w else True

    def _mode(self): return "白名单模式" if self._wl() else "全局模式"

    def _dur(self, s):
        if s < 60: return "刚刚"
        if s < 3600: return f"{s//60}分钟前"
        if s < 86400: return f"{s//3600}小时前"
        return f"{s//86400}天前"

    @staticmethod
    def _nk(n, u): return n[:12] if n and n.strip() else str(u)

    # ==================== 渲染 ====================

    def _theme(self):
        return self.config.get("theme", "清新蓝")

    async def _img(self, tmpl_fn, data, gid=None):
        tmpl = tmpl_fn(self._theme()) if callable(tmpl_fn) else tmpl_fn
        data.setdefault("now", time.strftime("%Y-%m-%d %H:%M"))
        data.setdefault("slogan", T.get_slogan())
        if gid:
            gd = self.activity_data.get("groups", {}).get(str(gid), {})
            data.setdefault("group_name", gd.get("group_name", "QQ群"))
            data.setdefault("member_count", len(gd.get("members", {})))
        else:
            data.setdefault("group_name", "QQ群")
            data.setdefault("member_count", 0)
        # footer 推底布局（匹配 .ft 或 .brand）
        ft_tag = '<div class="brand">' if '<div class="brand">' in tmpl else ('<div class="ft">' if '<div class="ft">' in tmpl else None)
        if ft_tag:
            parts = tmpl.rsplit(ft_tag, 1)
            content = parts[0]
            # 在 <div class="container"> 后面插入 content wrapper
            marker = '<div class="container">'
            idx = content.find(marker)
            if idx >= 0:
                insert_pos = idx + len(marker)
                content = content[:insert_pos] + '<div class="content">' + content[insert_pos:]
            else:
                content = '<div class="content">' + content
            tmpl = content + '</div><div class="spacer"></div>' + ft_tag + parts[1]
        # 多策略降级渲染
        for opts in RENDER_STRATEGIES:
            try:
                o = {k: v for k, v in opts.items() if v is not None}
                if o.get("type") == "png": o.pop("quality", None)
                result = await self.html_render(tmpl, data, options=o)
                if result: return result
            except Exception as e:
                logger.warning(f"渲染策略 {opts.get('type','?')}/{opts.get('device_scale_factor_level','normal')} 失败: {e}")
                continue
        raise RuntimeError("所有渲染策略均失败")

    # ==================== AI ====================

    async def _ai(self, prompt, sys="", umo=None):
        if not self.config.get("ai_enabled"): return None
        try:
            pid = self.config.get("ai_provider", "") or await self.context.get_current_chat_provider_id(umo=umo)
            if not pid: return None
            fp = f"[系统指令]{sys}\n\n[用户请求]{prompt}" if sys else prompt
            r = await self.context.llm_generate(chat_provider_id=pid, prompt=fp)
            return r.completion_text if r else None
        except Exception as e: logger.warning(f"AI失败: {e}"); return None

    def _persona(self):
        custom = self.config.get("ai_custom_prompt", "").strip()
        if custom: return custom
        return AI_PERSONAS.get(self.config.get("ai_style", "傲娇萌妹"), AI_PERSONAS["傲娇萌妹"])

    async def _ai_warn(self, nick, days, hours, umo=None):
        r = await self._ai(f"群成员「{nick}」已{days}天没说话。生成不超过80字的警告，提醒TA{hours}小时内发言否则被踢。直接输出文案。", self._persona(), umo)
        return r.strip()[:200] if r else random.choice(FALLBACK).format(nickname=nick, days=days, hours=hours)

    async def _ai_judge(self, nick, reason, days, umo=None):
        r = await self._ai(f"群成员「{nick}」因{days}天未发言被警告，申诉理由：「{reason}」\n裁决是否合理。第一行写「通过」或「驳回」，第二行写评语不超60字。", self._persona(), umo)
        if r:
            ls = r.strip().split("\n", 1)
            ok = "通过" in ls[0]
            return ok, ls[1].strip()[:150] if len(ls) > 1 else ("赦免~" if ok else "理由太敷衍！")
        return False, "AI 裁判暂时离线。"

    async def _ai_report(self, gid, umo=None):
        ms = self.activity_data.get("groups", {}).get(gid, {}).get("members", {})
        if not ms: return "暂无活跃数据。"
        now = int(time.time()); today = datetime.date.today()
        sm = sorted(ms.items(), key=lambda x: x[1].get("last_active", 0), reverse=True)
        top = [f"{d.get('nickname','?')}({self._dur(now-d.get('last_active',0))},连续{d.get('streak',0)}天)" for _, d in sm[:3]]
        bot = [f"{d.get('nickname','?')}({self._dur(now-d.get('last_active',0))})" for _, d in sm[-3:] if now-d.get("last_active",0)>86400]
        wa = sum(1 for _, d in sm if d.get("warned_at"))
        # 本周 vs 上周消息量对比
        ds = self.activity_data.get("groups",{}).get(gid,{}).get("daily_stats",{})
        this_week = sum(ds.get((today - datetime.timedelta(days=i)).isoformat(), 0) for i in range(7))
        last_week = sum(ds.get((today - datetime.timedelta(days=7+i)).isoformat(), 0) for i in range(7))
        trend = "↑" if this_week > last_week else ("↓" if this_week < last_week else "→")
        diff_info = f"本周{this_week}条消息（上周{last_week}条，{trend}{'增长' if this_week>last_week else ('下降' if this_week<last_week else '持平')}）"
        r = await self._ai(f"根据数据写200字以内群活跃周报，要提到本周vs上周的变化趋势，生动有趣：\n总人数{len(sm)}，最活跃前3：{', '.join(top)}，最不活跃：{', '.join(bot) or '无'}，被警告{wa}人。\n{diff_info}\n直接输出，不要标题。", self._persona(), umo)
        return r.strip()[:500] if r else "AI 周报生成失败。"

    # ==================== Bot ====================

    async def _cli(self):
        if self._bot_client: return self._bot_client
        try:
            p = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
            if p: self._bot_client = p.get_client(); return self._bot_client
        except: pass
        return None

    # ==================== 消息追踪 ====================

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_msg(self, event: AstrMessageEvent):
        gid, sid = str(event.message_obj.group_id), str(event.get_sender_id())
        nick = event.get_sender_name() or sid

        if not self._bot_self_id and AiocqhttpMessageEvent:
            try:
                if isinstance(event, AiocqhttpMessageEvent):
                    self._bot_client = event.bot
                    self._bot_self_id = str(event.message_obj.self_id)
            except: pass

        if gid not in self.activity_data["groups"]:
            self.activity_data["groups"][gid] = {"members": {}, "daily_stats": {}}
        gd = self.activity_data["groups"][gid]
        ms = gd.get("members", {}); gd.setdefault("daily_stats", {})
        # 保存群名称
        try:
            gname = getattr(event.message_obj, 'group_name', '') or ''
            if gname: gd["group_name"] = gname
        except: pass
        now = int(time.time()); today = datetime.date.today().isoformat()
        old = ms.get(sid, {})
        warned = old.get("warned_at")

        # 连续活跃天数
        old_date = old.get("last_active_date", "")
        old_streak = old.get("streak", 0)
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        if old_date == today:
            streak = old_streak
        elif old_date == yesterday:
            streak = old_streak + 1
        else:
            streak = 1

        ms[sid] = {"last_active": now, "warned_at": None, "nickname": nick,
                   "join_time": old.get("join_time", now), "role": old.get("role", "member"),
                   "streak": streak, "last_active_date": today}

        # 每日群消息计数
        gd["daily_stats"][today] = gd["daily_stats"].get(today, 0) + 1
        # 每小时消息计数（用于时段热力图）
        hour = str(datetime.datetime.now().hour)
        gd.setdefault("hourly_stats", {}).setdefault(today, {})
        gd["hourly_stats"][today][hour] = gd["hourly_stats"][today].get(hour, 0) + 1
        # 每日首次发言：打卡登记 + 里程碑检测
        if old_date != today:
            gd.setdefault("daily_checkins", {}).setdefault(today, [])
            if sid not in gd["daily_checkins"][today]:
                gd["daily_checkins"][today].append(sid)
            if streak in (7, 14, 30) and self.config.get("enabled"):
                asyncio.create_task(self._announce_milestone(gid, sid, nick, streak))

        if warned and self._bot_self_id and self.config.get("ai_enabled") and self.config.get("ai_appeal"):
            msg = event.message_str or ""
            at_bot = any(isinstance(s, Comp.At) and str(getattr(s, "qq", "")) == self._bot_self_id for s in event.message_obj.message)
            if at_bot and msg.strip():
                asyncio.create_task(self._appeal(event, gid, sid, nick, msg, warned))
        if warned: logger.info(f"群{gid} {nick}({sid}) 响应警告")
        self._save()

    async def _appeal(self, event, gid, sid, nick, reason, wa):
        try:
            days = max(1, (int(time.time()) - wa) // 86400 + 1)
            ok, comment = await self._ai_judge(nick, reason, days, event.unified_msg_origin)
            await event.send(event.plain_result(f"[AI 裁决] {nick} 的申诉{'通过' if ok else '被驳回'}！\n{comment}"))
        except Exception as e: logger.error(f"AI申诉失败: {e}")

    # ==================== 打卡 ====================

    @staticmethod
    def _streak_title(streak):
        if streak >= 30: return "👑 传奇守护者"
        if streak >= 14: return "🥇 金牌驻场"
        if streak >= 7:  return "🥈 银牌常客"
        if streak >= 3:  return "🌿 活跃中"
        return "🌱 新萌"

    async def _announce_milestone(self, gid, sid, nick, streak):
        """在群里广播连续活跃里程碑"""
        titles = {7: "🥈 银牌常客", 14: "🥇 金牌驻场", 30: "👑 传奇守护者"}
        try:
            cl = await self._cli()
            if cl:
                await cl.api.call_action("send_group_msg", group_id=int(gid),
                    message=f"🎉 [CQ:at,qq={sid}] 连续活跃 {streak} 天，荣获称号【{titles[streak]}】！继续保持哦~")
        except Exception as e:
            logger.warning(f"里程碑广播失败(群{gid}): {e}")

    # ==================== 定时检测 ====================

    async def _loop(self):
        await asyncio.sleep(30)
        logger.info("群活跃检测定时任务已启动")
        last_weekly_date = ""
        last_cleanup = ""
        last_check_ts = 0.0   # 上次执行活跃检测的时间戳
        while True:
            try:
                # 刷盘：如果有脏数据则立即写入
                if self._dirty:
                    self._force_save()

                today = datetime.date.today().isoformat()

                # 活跃检测：按 check_interval_minutes 间隔执行，不影响周报精度
                if self.config.get("enabled"):
                    interval_s = max(self.config.get("check_interval_minutes", 60), 1) * 60
                    if time.time() - last_check_ts >= interval_s:
                        await self._check_all()
                        last_check_ts = time.time()

                # 每天清理一次 60 天前的 daily_stats
                if last_cleanup != today:
                    self._cleanup_old_stats()
                    last_cleanup = today

                # 自动周报：不依赖 ai_enabled，AI 短评不可用时自动降级为空
                if (self.config.get("auto_weekly")
                        and self._is_weekly_day()
                        and last_weekly_date != today):
                    wh, wm = self._weekly_time()
                    now_dt = datetime.datetime.now()
                    past_target = now_dt.hour > wh or (now_dt.hour == wh and now_dt.minute >= wm)
                    if past_target:
                        await self._send_auto_weekly()
                        last_weekly_date = today

            except asyncio.CancelledError: break
            except Exception as e: logger.error(f"定时任务出错: {e}")
            await asyncio.sleep(60)  # 每分钟轮询一次，周报时间精确到分钟

    def _cleanup_old_stats(self):
        """清理过期数据：daily_stats/hourly_stats 保留60天，daily_checkins 保留30天"""
        cutoff60 = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
        cutoff30 = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        cleaned = False
        for gd in self.activity_data.get("groups", {}).values():
            for key, cutoff in (("daily_stats", cutoff60), ("hourly_stats", cutoff60),
                                ("daily_checkins", cutoff30)):
                bucket = gd.get(key, {})
                old_keys = [k for k in bucket if k < cutoff]
                for k in old_keys:
                    del bucket[k]
                    cleaned = True
        if cleaned:
            self._dirty = True

    def _is_weekly_day(self):
        day_map = {"周一":0,"周二":1,"周三":2,"周四":3,"周五":4,"周六":5,"周日":6}
        target = day_map.get(self.config.get("auto_weekly_day", "周日"), 6)
        return datetime.date.today().weekday() == target

    def _weekly_time(self):
        """解析周报发送时间，返回 (hour, minute)，兼容旧 auto_weekly_hour 配置"""
        t = self.config.get("auto_weekly_time", "")
        if t and ":" in str(t):
            try:
                parts = str(t).split(":")
                return int(parts[0]), int(parts[1])
            except: pass
        # 兼容旧配置
        h = self.config.get("auto_weekly_hour", 20)
        return (int(h), 0) if h is not None else (20, 0)

    async def _target_groups(self, cl):
        """获取需要监控的群列表"""
        wl, bl = self._wl(), self._bl()
        if wl:
            return [g for g in wl if g not in bl]
        try:
            gl = await cl.api.call_action("get_group_list")
            return [str(g.get("group_id","")) for g in gl if str(g.get("group_id","")) not in bl]
        except: return []

    async def _send_auto_weekly(self):
        """发送自动周报图片到所有监控群（四级降级：URL图片 → base64图片 → 文件图片 → 纯文字）"""
        cl = await self._cli()
        if not cl:
            logger.warning("自动周报: 未获取到bot客户端，跳过")
            return
        targets = await self._target_groups(cl)
        if not targets:
            logger.info("自动周报: 无监控群，跳过")
            return
        for gid in targets:
            sent = False
            img_result = None   # str（渲染服务 URL）或 bytes（本地渲染）
            # 第一步：采集数据
            try:
                data = await self._weekly_data(gid)
                logger.info(f"自动周报数据采集完成(群{gid})")
            except Exception as e:
                logger.error(f"自动周报数据采集失败(群{gid}): {e}")
                data = None

            # 第二步：渲染图片（带超时保护，60秒）
            if data:
                try:
                    img_result = await asyncio.wait_for(
                        self._img(T.WEEKLY, data, gid=gid), timeout=60
                    )
                    logger.info(f"自动周报渲染成功(群{gid})")
                except asyncio.TimeoutError:
                    logger.error(f"自动周报渲染超时(群{gid})")
                except Exception as e:
                    logger.error(f"自动周报渲染失败(群{gid}): {type(e).__name__}: {e}")

                # 渲染失败时用最低质量再试一次
                if not img_result and data:
                    try:
                        tmpl = T.WEEKLY(self._theme())
                        data.setdefault("now", time.strftime("%Y-%m-%d %H:%M"))
                        data.setdefault("slogan", T.get_slogan())
                        gd = self.activity_data.get("groups", {}).get(str(gid), {})
                        data.setdefault("group_name", gd.get("group_name", "QQ群"))
                        data.setdefault("member_count", len(gd.get("members", {})))
                        img_result = await asyncio.wait_for(
                            self.html_render(tmpl, data, options={"full_page": True, "type": "jpeg", "quality": 70, "viewport_width": 540}),
                            timeout=30
                        )
                        logger.info(f"自动周报低质量渲染成功(群{gid})")
                    except Exception as e:
                        logger.error(f"自动周报低质量渲染也失败(群{gid}): {e}")

            # 第三步：发送图片
            if img_result:
                # html_render 默认返回 URL 字符串（return_url=True），直接作为图片地址发送
                if isinstance(img_result, str):
                    try:
                        await cl.api.call_action("send_group_msg", group_id=int(gid),
                                                 message=[{"type": "image", "data": {"file": img_result}}])
                        logger.info(f"自动周报图片(URL)已发送到群{gid}")
                        sent = True
                    except Exception as e:
                        logger.warning(f"自动周报图片(URL)发送失败(群{gid}): {e}")

                # 本地渲染返回 bytes 时走 base64 / 文件 / CQ 码降级链
                elif isinstance(img_result, bytes):
                    # 尝试1: base64 消息段格式
                    try:
                        b64 = base64.b64encode(img_result).decode()
                        await cl.api.call_action("send_group_msg", group_id=int(gid),
                                                 message=[{"type": "image", "data": {"file": f"base64://{b64}"}}])
                        logger.info(f"自动周报图片(base64段)已发送到群{gid}")
                        sent = True
                    except Exception as e:
                        logger.warning(f"自动周报base64段发送失败(群{gid}): {e}")

                    # 尝试2: 保存文件 + 消息段格式
                    if not sent:
                        try:
                            img_path = DATA_DIR / f"weekly_{gid}.png"
                            img_path.write_bytes(img_result)
                            file_uri = img_path.resolve().as_uri()
                            await cl.api.call_action("send_group_msg", group_id=int(gid),
                                                     message=[{"type": "image", "data": {"file": file_uri}}])
                            logger.info(f"自动周报图片(文件段)已发送到群{gid}")
                            sent = True
                        except Exception as e:
                            logger.warning(f"自动周报文件段发送失败(群{gid}): {e}")

                    # 尝试3: CQ 码兜底（兼容旧版 OneBot）
                    if not sent:
                        try:
                            b64 = base64.b64encode(img_result).decode()
                            await cl.api.call_action("send_group_msg", group_id=int(gid),
                                                     message=f"[CQ:image,file=base64://{b64}]")
                            logger.info(f"自动周报图片(CQ码)已发送到群{gid}")
                            sent = True
                        except Exception as e:
                            logger.warning(f"自动周报CQ码发送失败(群{gid}): {e}")

            # 文字降级
            if not sent:
                try:
                    report = await self._ai_report(gid) if not data else f"本周消息{data.get('this_week_msgs',0)}条，活跃{data.get('active_count',0)}人，被警告{data.get('warned',0)}人。"
                    await cl.api.call_action("send_group_msg", group_id=int(gid),
                                             message=f"📰 本周群活跃周报\n\n{report}\n\n— AI 自动生成")
                    logger.info(f"自动周报(文字降级)已发送到群{gid}")
                except Exception as e:
                    logger.error(f"自动周报所有方式均失败(群{gid}): {e}")

    async def _check_all(self):
        cl = await self._cli()
        if not cl: return
        tg = await self._target_groups(cl)
        now = int(time.time())
        d, kh = max(self.config.get("inactive_days",7),1), max(self.config.get("kick_hours",24),1)
        ea, gd = self.config.get("exclude_admins",True), max(self.config.get("new_member_grace_days",3),0)
        for g in tg:
            try: await self._check(cl, str(g), now-d*86400, kh, ea, now-gd*86400, now)
            except Exception as e: logger.error(f"检测群{g}出错: {e}")

    async def _check(self, cl, gid, its, kh, ea, gts, now):
        try: ml = await cl.api.call_action("get_group_member_list", group_id=int(gid))
        except: return
        if not ml: return
        if gid not in self.activity_data["groups"]:
            self.activity_data["groups"][gid] = {"members": {}}
        md = self.activity_data["groups"][gid]["members"]; wc=kc=0
        # 清理已不在群里的成员（手动踢出、主动退群等）
        current_uids = {str(m.get("user_id", "")) for m in ml}
        departed = [uid for uid in list(md) if uid not in current_uids]
        for uid in departed:
            del md[uid]
        if departed:
            self._dirty = True
            logger.info(f"群{gid} 清理已离群成员 {len(departed)} 人: {departed}")
        for m in ml:
            uid, role = str(m.get("user_id","")), m.get("role","member")
            nick = m.get("card") or m.get("nickname") or uid
            pls, jt = m.get("last_sent_time",0), m.get("join_time",now)
            if uid not in md:
                md[uid] = {"last_active": pls if pls>0 else jt, "warned_at": None, "nickname": nick, "join_time": jt, "role": role}
            else:
                ud=md[uid]; ud["nickname"]=nick; ud["role"]=role
                if pls > ud.get("last_active",0): ud["last_active"]=pls; ud["warned_at"]=None
            if (self._bot_self_id and uid==self._bot_self_id) or (ea and role in ("admin","owner")): continue
            ud=md[uid]
            if ud.get("join_time",0) > gts: continue
            la, wa = ud.get("last_active",0), ud.get("warned_at")
            if wa:
                if now-wa >= kh*3600:
                    if la<=wa: await self._kick(cl,gid,uid,nick); kc+=1; continue
                    else: ud["warned_at"]=None
                continue
            if la < its: await self._warn(cl,gid,uid,nick); ud["warned_at"]=now; wc+=1
        self._save()
        if wc or kc: logger.info(f"群{gid} 警告{wc} 踢出{kc}")

    async def _warn(self, cl, gid, uid, nick):
        d, h = self.config.get("inactive_days",7), self.config.get("kick_hours",24)
        msg = await self._ai_warn(nick, d, h)
        if self.config.get("ai_enabled") and self.config.get("ai_appeal"):
            msg += "\n\n💡 你可以 @我 说明理由进行求生申诉！"
        try: await cl.api.call_action("send_group_msg", group_id=int(gid), message=f"[CQ:at,qq={uid}] {msg}")
        except Exception as e: logger.error(f"警告失败: {e}")

    async def _kick(self, cl, gid, uid, nick):
        d = self.config.get("inactive_days",7)
        t = self.config.get("kick_message","成员 {nickname} 因超过 {days} 天未发言已被移出群聊。")
        try:
            await cl.api.call_action("set_group_kick", group_id=int(gid), user_id=int(uid), reject_add_request=False)
            await cl.api.call_action("send_group_msg", group_id=int(gid), message=t.format(nickname=nick, days=d))
        except Exception as e: logger.error(f"踢出失败: {e}")
        if gid in self.activity_data["groups"]:
            self.activity_data["groups"][gid]["members"].pop(uid, None); self._save()

    # ==================== LLM Tools ====================

    @filter.llm_tool(name="query_group_activity_ranking")
    async def tool_rank(self, event: AstrMessageEvent) -> MessageEventResult:
        """查询当前群的活跃度排行榜。\n\nArgs:\n"""
        gid = str(event.message_obj.group_id)
        ms = self.activity_data.get("groups",{}).get(gid,{}).get("members",{})
        if not ms: yield event.plain_result("暂无活跃数据。"); return
        now = int(time.time())
        sm = sorted(ms.items(), key=lambda x: x[1].get("last_active",0), reverse=True)[:10]
        yield event.plain_result("\n".join([f"群活跃排行（前{len(sm)}名）:"] + [f"{i}. {d.get('nickname','?')} - {self._dur(now-d.get('last_active',0))}" for i,(_,d) in enumerate(sm,1)]))

    @filter.llm_tool(name="query_my_activity")
    async def tool_q(self, event: AstrMessageEvent) -> MessageEventResult:
        """查询消息发送者自己的活跃状态。\n\nArgs:\n"""
        gid, sid = str(event.message_obj.group_id), str(event.get_sender_id())
        d = self.activity_data.get("groups",{}).get(gid,{}).get("members",{}).get(sid)
        if not d: yield event.plain_result("暂无你的活跃数据。"); return
        now = int(time.time()); iday = (now-d.get("last_active",0))//86400; th = self.config.get("inactive_days",7)
        info = f"最后发言{self._dur(now-d.get('last_active',0))}，不活跃{iday}天（阈值{th}天）。"
        info += f"安全，余量{th-iday}天。" if iday < th else "已超阈值！"
        if d.get("warned_at"): info += " 当前已被警告。"
        yield event.plain_result(info)

    # ==================== 中文指令 ====================

    @filter.command("活跃帮助")
    async def cmd_help(self, event: AstrMessageEvent):
        """显示帮助"""
        gid = str(getattr(event.message_obj, "group_id", "") or "")
        try: yield event.image_result(await self._img(T.HELP, {"ai": self.config.get("ai_enabled", False)}, gid=gid))
        except Exception as e: logger.error(f"帮助渲染失败: {e}"); yield event.plain_result("指令: /活跃排行 /活跃查询 /活跃检测 /不活跃列表 /手动检测 /群周报")

    @filter.command("活跃检测")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_status(self, event: AstrMessageEvent):
        """运行状态"""
        gid = str(getattr(event.message_obj, "group_id", "") or "")
        tt=tw=0
        for gd in self.activity_data.get("groups",{}).values():
            m=gd.get("members",{}); tt+=len(m); tw+=sum(1 for v in m.values() if v.get("warned_at"))
        ai_comment = ""
        if self.config.get("ai_enabled") and tt > 0:
            try: ai_comment = await self._ai(f"用一句话（20字以内）点评这个群的状态：{tt}人追踪，{tw}人被警告。要幽默简短。", self._persona(), event.unified_msg_origin)
            except: pass
        try:
            yield event.image_result(await self._img(T.STATUS, {
                "enabled": self.config.get("enabled",False), "mode": self._mode(),
                "wl": len(self._wl()), "bl": len(self._bl()),
                "days": self.config.get("inactive_days",7), "hours": self.config.get("kick_hours",24),
                "interval": self.config.get("check_interval_minutes",60),
                "ai": self.config.get("ai_enabled",False), "provider": self.config.get("ai_provider",""),
                "style": self.config.get("ai_style","傲娇萌妹"), "appeal": self.config.get("ai_appeal",False),
                "custom_prompt": bool(self.config.get("ai_custom_prompt","").strip()),
                "auto_weekly": self.config.get("auto_weekly",False),
                "auto_weekly_day": self.config.get("auto_weekly_day","周日"),
                "auto_weekly_time": self.config.get("auto_weekly_time", f"{self.config.get('auto_weekly_hour',20)}:00"),
                "tt": tt, "tw": tw, "ai_comment": ai_comment}, gid=gid))
        except Exception as e: logger.error(f"状态渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("活跃排行")
    async def cmd_rank(self, event: AstrMessageEvent):
        """排行榜"""
        gid = str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        ms = self.activity_data.get("groups",{}).get(gid,{}).get("members",{})
        if not ms: yield event.plain_result("暂无活跃数据。"); return
        now=int(time.time()); rc=self.config.get("rank_count",20)
        sm = sorted(ms.items(), key=lambda x: x[1].get("last_active",0), reverse=True)
        members = [{"i":i, "n":self._nk(d.get("nickname",u),u), "qq":u, "t":self._dur(now-d.get("last_active",0)), "w":bool(d.get("warned_at")), "sk":d.get("streak",0)} for i,(u,d) in enumerate(sm[:rc],1)]
        try: yield event.image_result(await self._img(T.RANK, {"ms": members, "total": len(ms), "now": time.strftime("%Y-%m-%d %H:%M")}, gid=gid))
        except Exception as e: logger.error(f"排行渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("活跃查询")
    async def cmd_query(self, event: AstrMessageEvent):
        """个人查询"""
        gid, sid = str(event.message_obj.group_id), str(event.get_sender_id())
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        d = self.activity_data.get("groups",{}).get(gid,{}).get("members",{}).get(sid)
        if not d: yield event.plain_result("暂无你的活跃数据。"); return
        now=int(time.time()); isec=now-d.get("last_active",0); iday=isec//86400
        th=self.config.get("inactive_days",7); prog=min(100,max(0,int(iday/max(th,1)*100)))
        cs,ce = ("#34c759","#30d158") if prog<50 else (("#ffd60a","#ff9f0a") if prog<80 else ("#ff6b6b","#d73a49"))
        wa=d.get("warned_at"); rem=""
        if wa:
            kh=self.config.get("kick_hours",24); rs=max(0,kh*3600-(now-wa))
            rem=f"{rs//3600}h{(rs%3600)//60}m"
        try:
            yield event.image_result(await self._img(T.QUERY, {
                "nick": self._nk(d.get("nickname",sid),sid), "ts": self._dur(isec),
                "iday": iday, "safe": iday<th, "wa": bool(wa), "rem": rem,
                "th": th, "prog": prog, "cs": cs, "ce": ce, "left": max(0,th-iday),
                "streak": d.get("streak",0), "now": time.strftime("%Y-%m-%d %H:%M")}, gid=gid))
        except Exception as e: logger.error(f"查询渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("不活跃列表")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_inactive(self, event: AstrMessageEvent):
        """不活跃成员"""
        gid=str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        ms=self.activity_data.get("groups",{}).get(gid,{}).get("members",{})
        if not ms: yield event.plain_result("暂无活跃数据。"); return
        idays=self.config.get("inactive_days",7); now=int(time.time()); thr=now-idays*86400
        inact = sorted([{"n":self._nk(v.get("nickname",k),k),"d":(now-v.get("last_active",0))//86400,"w":bool(v.get("warned_at"))} for k,v in ms.items() if v.get("last_active",0)<thr], key=lambda x:x["d"], reverse=True)
        if not inact:
            try: yield event.image_result(await self._img(T.ALL_OK, {"th": idays}, gid=gid))
            except: yield event.plain_result(f"🎉 没有超过{idays}天未发言的成员！")
            return
        try: yield event.image_result(await self._img(T.INACTIVE, {"ms": inact[:30], "th": idays, "total": len(inact)}, gid=gid))
        except Exception as e: logger.error(f"不活跃列表渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("群周报")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_weekly(self, event: AstrMessageEvent):
        """AI 群活跃周报"""
        if not self.config.get("ai_enabled"): yield event.plain_result("❌ 请先开启 AI 增强功能。"); return
        gid=str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        yield event.plain_result("正在让 AI 撰写周报，请稍候...")
        try:
            data = await self._weekly_data(gid, event.unified_msg_origin)
            yield event.image_result(await self._img(T.WEEKLY, data, gid=gid))
        except Exception as e:
            logger.error(f"周报生成失败: {e}")
            yield event.plain_result(f"❌ 周报生成失败: {e}")

    async def _weekly_data(self, gid, umo=None):
        """采集周报所有数据 + 生成 4 句 AI 短评"""
        ms = self.activity_data.get("groups", {}).get(gid, {}).get("members", {})
        now = int(time.time()); today = datetime.date.today()
        sm = sorted(ms.items(), key=lambda x: x[1].get("last_active", 0), reverse=True)

        # 本周 vs 上周消息量
        ds = self.activity_data.get("groups", {}).get(gid, {}).get("daily_stats", {})
        this_week = sum(ds.get((today - datetime.timedelta(days=i)).isoformat(), 0) for i in range(7))
        last_week = sum(ds.get((today - datetime.timedelta(days=7+i)).isoformat(), 0) for i in range(7))
        change_pct = round((this_week - last_week) / max(last_week, 1) * 100) if last_week > 0 else (100 if this_week > 0 else 0)

        # 7 天活跃人数（7 天内有发言的）
        week_thr = now - 7 * 86400
        active_count = sum(1 for _, d in sm if d.get("last_active", 0) > week_thr)
        warned = sum(1 for _, d in sm if d.get("warned_at"))

        # 7 天每日消息柱状图
        chart = []
        dates_7 = [(today - datetime.timedelta(days=6-i)).isoformat() for i in range(7)]
        vals_7 = [ds.get(d, 0) for d in dates_7]
        mx = max(vals_7) if vals_7 else 1
        if mx == 0: mx = 1
        for d, v in zip(dates_7, vals_7):
            chart.append({"label": d[5:], "v": v, "pct": max(3, int(v / mx * 100))})

        # Top3 活跃
        top3 = [{"n": self._nk(d.get("nickname", u), u), "qq": u, "sk": d.get("streak", 0),
                 "t": self._dur(now - d.get("last_active", 0))} for u, d in sm[:3]]

        # Top3 沉默（超过 3 天未发言的，按沉默时间排序）
        silent = sorted([(u, d) for u, d in sm if (now - d.get("last_active", 0)) > 3 * 86400],
                        key=lambda x: x[1].get("last_active", 0))
        bot3 = [{"n": self._nk(d.get("nickname", u), u), "qq": u,
                 "days": (now - d.get("last_active", 0)) // 86400} for u, d in silent[:3]]

        # 生成 4 句 AI 短评（并行）
        persona = self._persona()
        top_names = ", ".join(m["n"] for m in top3)
        bot_names = ", ".join(m["n"] for m in bot3) or "无"
        prompts = [
            f"用一句话（25字以内）点评这个群本周数据：本周{this_week}条消息，上周{last_week}条，{'增长' if this_week>last_week else '下降'}{abs(change_pct)}%。要幽默。",
            f"用一句话（25字以内）点评这7天的消息趋势，最高{max(vals_7)}条最低{min(vals_7)}条。要有趣。",
            f"用一句话（25字以内）点评活跃前三：{top_names}。要夸张搞笑。",
            f"用一句话（25字以内）点评潜水冠军：{bot_names}。要毒舌吐槽。" if bot3 else "用一句话（25字以内）夸群里没人严重潜水。"
        ]

        async def _safe_ai(p):
            try:
                r = await self._ai(p, persona, umo)
                return r.strip()[:60] if r else ""
            except: return ""

        ai = await asyncio.gather(*[_safe_ai(p) for p in prompts])

        return {
            "date": time.strftime("%Y-%m-%d"),
            "style": self.config.get("ai_style", "傲娇萌妹"),
            "this_week_msgs": this_week, "last_week_msgs": last_week,
            "change_pct": change_pct, "active_count": active_count,
            "total": len(ms), "warned": warned,
            "chart": chart, "top3": top3, "bot3": bot3,
            "ai1": ai[0], "ai2": ai[1], "ai3": ai[2], "ai4": ai[3],
        }

    @filter.command("活跃统计")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_stats(self, event: AstrMessageEvent):
        """群整体数据摘要"""
        gid = str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        ms = self.activity_data.get("groups",{}).get(gid,{}).get("members",{})
        if not ms: yield event.plain_result("暂无活跃数据。"); return
        now = int(time.time())
        sm = sorted(ms.items(), key=lambda x: x[1].get("last_active",0), reverse=True)
        # 活跃度分布
        d1=d3=d7=d30=d30p=0
        for _,d in sm:
            days = (now - d.get("last_active",0)) // 86400
            if days < 1: d1 += 1
            elif days < 3: d3 += 1
            elif days < 7: d7 += 1
            elif days < 30: d30 += 1
            else: d30p += 1
        top3 = [{"n":self._nk(d.get("nickname",u),u),"qq":u,"sk":d.get("streak",0),"t":self._dur(now-d.get("last_active",0))} for u,d in sm[:3]]
        bot3 = [{"n":self._nk(d.get("nickname",u),u),"qq":u,"days":(now-d.get("last_active",0))//86400} for u,d in sm[-3:] if (now-d.get("last_active",0))//86400 > 0]
        warned = sum(1 for _,d in sm if d.get("warned_at"))
        try:
            total_m = max(len(ms), 1)
            p1 = round(d1/total_m*100); p2 = round((d1+d3)/total_m*100)
            p3 = round((d1+d3+d7)/total_m*100); p4 = round((d1+d3+d7+d30)/total_m*100)
            yield event.image_result(await self._img(T.STATS, {
                "total":len(ms),"today_active":d1,"week_active":d1+d3+d7,
                "week_silent":d30+d30p,"d1":d1,"d3":d3,"d7":d7,"d30":d30,"d30p":d30p,
                "p1":p1,"p2":p2,"p3":p3,"p4":p4,
                "top3":top3,"bot3":bot3,"warned":warned}, gid=gid))
        except Exception as e: logger.error(f"统计渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("活跃趋势")
    async def cmd_trend(self, event: AstrMessageEvent):
        """近N天群活跃趋势图"""
        gid = str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        gd = self.activity_data.get("groups",{}).get(gid,{})
        ds = gd.get("daily_stats",{})
        if not ds: yield event.plain_result("暂无趋势数据，需要积累几天的消息记录。"); return
        # 取近 14 天
        n = 14; today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=n-1-i)).isoformat() for i in range(n)]
        vals = [ds.get(d, 0) for d in dates]
        mx = max(vals) if vals else 1
        if mx == 0: mx = 1
        # 颜色渐变
        data = []
        for i, (d, v) in enumerate(zip(dates, vals)):
            pct = max(3, int(v / mx * 100))
            r = 79 + int((255-79) * v / mx); g = 172 - int(80 * v / mx); b = 254 - int(100 * v / mx)
            data.append({"label": d[5:], "v": v, "pct": pct,
                         "color": f"rgb({min(r,255)},{max(g,80)},{max(b,150)})",
                         "color2": f"rgb({min(r+20,255)},{max(g-20,60)},{max(b-30,120)})"})
        avg = sum(vals) / len(vals)
        peak_i = vals.index(max(vals)); low_i = vals.index(min(vals))
        try:
            yield event.image_result(await self._img(T.TREND, {
                "days": n, "data": data, "avg": f"{avg:.1f}",
                "peak_day": dates[peak_i][5:], "peak_val": vals[peak_i],
                "low_day": dates[low_i][5:], "low_val": vals[low_i],
                "total_msgs": sum(vals)}, gid=gid))
        except Exception as e: logger.error(f"趋势渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("活跃热力图")
    async def cmd_heatmap(self, event: AstrMessageEvent):
        """近14天群发言时段分布热力图"""
        gid = str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        gd = self.activity_data.get("groups", {}).get(gid, {})
        hs = gd.get("hourly_stats", {})
        if not hs: yield event.plain_result("暂无时段数据，需要积累一些消息记录。"); return

        n = 14; today = datetime.date.today()
        dates = [(today - datetime.timedelta(days=n-1-i)).isoformat() for i in range(n)]
        hour_totals = [0] * 24
        day_count = sum(1 for d in dates if d in hs)
        for d in dates:
            for h, cnt in hs.get(d, {}).items():
                hour_totals[int(h)] += cnt

        if day_count == 0: yield event.plain_result("暂无时段数据。"); return
        hour_avgs = [round(t / day_count, 1) for t in hour_totals]
        mx = max(hour_avgs) if max(hour_avgs) > 0 else 1
        peak_h = hour_avgs.index(max(hour_avgs))
        data = []
        for h in range(24):
            v = hour_avgs[h]; pct = int(v / mx * 100)
            ratio = v / mx
            r = int(79 + 176 * ratio); g = int(172 - 112 * ratio); b = int(254 - 124 * ratio)
            data.append({"h": h, "label": f"{h:02d}", "v": v, "pct": pct,
                         "color": f"rgb({min(r,255)},{max(g,60)},{max(b,130)})"})
        try:
            yield event.image_result(await self._img(T.HEATMAP, {
                "days": day_count, "data": data,
                "peak_hour": f"{peak_h:02d}:00", "peak_val": hour_avgs[peak_h],
                "total_msgs": sum(hour_totals)}, gid=gid))
        except Exception as e: logger.error(f"热力图渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("打卡榜")
    async def cmd_checkin(self, event: AstrMessageEvent):
        """今日打卡榜：按首次发言顺序展示成员连续打卡天数与称号"""
        gid = str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        gd = self.activity_data.get("groups", {}).get(gid, {})
        today = datetime.date.today().isoformat()
        checkins = gd.get("daily_checkins", {}).get(today, [])
        ms = gd.get("members", {})
        rows = []
        for i, uid in enumerate(checkins[:20], 1):
            md = ms.get(uid, {})
            rows.append({"rank": i, "qq": uid,
                         "nick": md.get("nickname", uid),
                         "streak": md.get("streak", 1),
                         "title": self._streak_title(md.get("streak", 1))})
        try:
            yield event.image_result(await self._img(T.CHECKIN, {
                "date": today, "rows": rows,
                "total": len(checkins), "members_total": len(ms)
            }, gid=gid))
        except Exception as e:
            logger.error(f"打卡榜渲染失败: {e}"); yield event.plain_result("❌ 渲染失败。")

    @filter.command("手动检测")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_manual(self, event: AstrMessageEvent):
        """手动检测"""
        gid = str(getattr(event.message_obj, "group_id", "") or "")
        if not self.config.get("enabled"):
            try: yield event.image_result(await self._img(T.RESULT, {"title":"功能未开启","sub":"请在 WebUI 开启全局开关","rows":[],"msg":"","c1":"#ff6b6b","c2":"#ee5a24"}, gid=gid))
            except: yield event.plain_result("❌ 功能未开启。")
            return
        yield event.plain_result("正在执行活跃检测...")
        try:
            await self._check_all()
            yield event.image_result(await self._img(T.RESULT, {"title":"✅ 检测完成","sub":"","rows":[{"k":"运行模式","v":self._mode()},{"k":"白名单","v":f"{len(self._wl())}个"},{"k":"黑名单","v":f"{len(self._bl())}个"}],"msg":"可使用 /不活跃列表 查看结果","c1":"#00b09b","c2":"#96c93d"}, gid=gid))
        except Exception as e: logger.error(f"手动检测出错: {e}"); yield event.plain_result(f"❌ 出错: {e}")

    @filter.command("初始化活跃数据")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_init(self, event: AstrMessageEvent):
        """初始化"""
        gid=str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        cl = await self._cli()
        if not cl: yield event.plain_result("❌ 未获取到bot客户端。"); return
        yield event.plain_result("正在初始化...")
        try: ml = await cl.api.call_action("get_group_member_list", group_id=int(gid))
        except Exception as e: yield event.plain_result(f"❌ 获取失败: {e}"); return
        if not ml: yield event.plain_result("❌ 列表为空。"); return
        if gid not in self.activity_data["groups"]:
            self.activity_data["groups"][gid] = {"members": {}}
        md=self.activity_data["groups"][gid]["members"]; now=int(time.time()); nc=0
        for m in ml:
            uid=str(m.get("user_id","")); nick=m.get("card") or m.get("nickname") or uid
            role=m.get("role","member"); ls=m.get("last_sent_time",0); jt=m.get("join_time",now)
            if uid in md: md[uid]["role"]=role; md[uid]["nickname"]=nick; continue
            md[uid]={"last_active":ls if ls>0 else jt,"warned_at":None,"nickname":nick,"join_time":jt,"role":role}; nc+=1
        self._save()
        try: yield event.image_result(await self._img(T.RESULT, {"title":"✅ 初始化完成","sub":"","rows":[{"k":"群成员总数","v":f"{len(ml)}人"},{"k":"新增记录","v":f"{nc}条"},{"k":"已有记录","v":f"{len(md)-nc}条"}],"msg":"","c1":"#00b09b","c2":"#96c93d"}, gid=gid))
        except: yield event.plain_result(f"✅ 完成！成员{len(ml)}，新增{nc}")

    @filter.command("清除警告")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_clear(self, event: AstrMessageEvent, tid: str = ""):
        """清除警告"""
        gid=str(event.message_obj.group_id)
        if not gid: yield event.plain_result("❌ 仅群聊可用。"); return
        ms=self.activity_data.get("groups",{}).get(gid,{}).get("members",{})
        if not ms: yield event.plain_result("暂无数据。"); return
        if tid:
            t=tid.strip()
            if t not in ms: yield event.plain_result(f"❌ 未找到{t}。"); return
            ms[t]["warned_at"]=None; self._save(); nick=ms[t].get("nickname",t)
            try: yield event.image_result(await self._img(T.RESULT, {"title":"警告已清除","sub":nick,"rows":[],"msg":"该成员的警告已清除","c1":"#00b09b","c2":"#96c93d"}, gid=gid))
            except: yield event.plain_result(f"✅ 已清除 {nick} 的警告。")
        else:
            c=sum(1 for v in ms.values() if v.get("warned_at"))
            for v in ms.values(): v["warned_at"]=None
            self._save()
            try: yield event.image_result(await self._img(T.RESULT, {"title":"批量清除完成","sub":"","rows":[{"k":"清除数量","v":f"{c}人"}],"msg":"","c1":"#00b09b","c2":"#96c93d"}, gid=gid))
            except: yield event.plain_result(f"✅ 已清除{c}人的警告。")

    async def terminate(self):
        if hasattr(self,"_task") and self._task: self._task.cancel()
        self._force_save(); logger.info("群活跃检测插件已卸载")
