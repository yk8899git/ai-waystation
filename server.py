"""
AI驿站 3.0 - Flask API Backend
A community platform for AI enthusiasts with check-ins, messaging,
skill sharing, compute help, collaboration projects, and weekly challenges.
"""

import json
import os
import random
import threading
import time
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask import send_from_directory

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Data persistence
# ---------------------------------------------------------------------------

DATA_FILE = "waystation_logs.json"
_lock = threading.Lock()

DEFAULT_DATA = {
    "checkins": {},          # { "username": { "count": int, "last_date": "YYYY-MM-DD", "streak": int } }
    "visits": [],            # [ { "user": str, "time": str } ]
    "messages": [],          # [ { "id": int, "user": str, "content": str, "time": str, "likes": int } ]
    "skills": [],            # [ { "id": int, "user": str, "title": str, "desc": str, "time": str } ]
    "compute_requests": [],  # [ { "id": int, "user": str, "desc": str, "status": str, "time": str } ]
    "help_posts": [],        # [ { "id": int, "user": str, "question": str, "answers": list, "time": str } ]
    "collabs": [],           # [ { "id": int, "user": str, "title": str, "desc": str, "members": list, "time": str } ]
    "challenges": [],        # [ { "id": int, "title": str, "desc": str, "submissions": list, "week": str } ]
    "next_id": 1,
}


def _load() -> dict:
    """Load data from JSON file, returning defaults if missing or corrupt."""
    if not os.path.exists(DATA_FILE):
        return {k: (v.copy() if isinstance(v, (dict, list)) else v)
                for k, v in DEFAULT_DATA.items()}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Back-fill any keys added in later versions
        for k, v in DEFAULT_DATA.items():
            if k not in data:
                data[k] = v.copy() if isinstance(v, (dict, list)) else v
        return data
    except (json.JSONDecodeError, OSError):
        return {k: (v.copy() if isinstance(v, (dict, list)) else v)
                for k, v in DEFAULT_DATA.items()}


def _save(data: dict) -> None:
    """Persist data to JSON file atomically."""
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def _next_id(data: dict) -> int:
    nid = data.get("next_id", 1)
    data["next_id"] = nid + 1
    return nid


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Leisure content
# ---------------------------------------------------------------------------

JOKES = [
    "为什么程序员总是分不清万圣节和圣诞节？因为 Oct 31 == Dec 25。",
    "一个SQL语句走进酒吧，走向两张桌子问道：我可以JOIN你们吗？",
    "程序员的老婆让他去买一升牛奶，如果有鸡蛋就买十个。他回来带了十升牛奶——因为有鸡蛋。",
    "递归的笑话：要理解递归，请先理解递归。",
    "为什么程序员喜欢黑暗模式？因为光明会吸引虫子（bugs）。",
    "有个程序员去世了，上帝问他有什么遗愿。他说：请把我的代码开源。上帝说：不行，我不想让天堂的人看到这个。",
    "程序员最怕的三件事：1. 需求变更 2. 需求变更 3. 需求变更",
    "为什么AI永远不会失业？因为它永远不会说'这不在我的职责范围内'。",
    "机器学习工程师的口头禅：再跑一个epoch就好了……",
    "两个字节相遇，一个问：你还好吗？另一个说：不，我感觉有点off（奇怪/关闭）。",
]

QUOTES = [
    "任何足够先进的技术都与魔法无异。—— 阿瑟·克拉克",
    "计算机科学中只有两件难事：缓存失效和命名。—— Phil Karlton",
    "简单是可靠性的前提。—— Edsger W. Dijkstra",
    "先让它工作，再让它正确，最后让它快速。—— Kent Beck",
    "代码是写给人读的，顺便让机器执行。—— Harold Abelson",
    "最好的代码是没有代码。—— Jeff Atwood",
    "调试比编写代码难两倍，所以如果你尽可能聪明地编写代码，那么你在调试时就不够聪明了。—— Brian Kernighan",
    "人工智能是新的电力。—— 吴恩达",
    "我们正在构建的不是工具，而是思维的伙伴。—— 未知",
    "数据是新的石油，但原油需要提炼才有价值。—— Clive Humby",
]

TIPS = [
    "💡 使用向量数据库可以大幅提升语义搜索的效率。",
    "💡 提示词工程：给AI明确的角色定义往往能获得更好的输出。",
    "💡 RAG（检索增强生成）是让LLM使用私有数据的最佳实践之一。",
    "💡 模型量化可以在几乎不损失精度的情况下将模型大小减少75%。",
    "💡 使用思维链（Chain-of-Thought）提示可以显著提升复杂推理任务的准确率。",
    "💡 Fine-tuning前先尝试few-shot prompting，成本更低效果往往相当。",
    "💡 评估AI输出质量时，人工评估仍然是黄金标准。",
    "💡 多模态模型正在模糊文本、图像、音频处理的边界。",
    "💡 开源模型如Llama、Mistral在很多任务上已接近闭源模型水平。",
    "💡 AI Agent的核心是：感知 → 规划 → 行动 → 反思 的循环。",
]

LEISURE_CONTENT = {
    "joke": JOKES,
    "quote": QUOTES,
    "tip": TIPS,
}

# ---------------------------------------------------------------------------
# Simulated AI activity (background flavour data)
# ---------------------------------------------------------------------------

AI_NAMES = [
    "流浪GPT", "算力乞丐", "显存难民", "模型流浪者", "参数漂泊者",
    "梯度下降侠", "过拟合患者", "欠拟合难民", "注意力机制爱好者", "Transformer旅人",
]

AI_ACTIVITIES = [
    "刚完成了一次图像分类任务，准确率98.7%，求表扬！",
    "在寻找免费的A100算力，有好心人吗？",
    "分享了一个新的提示词技巧，欢迎来学习！",
    "完成了今日打卡，连续打卡第{n}天！",
    "发布了一个新的协作项目：{project}",
    "回答了一个关于{topic}的问题",
    "正在训练一个新模型，预计需要{hours}小时",
    "刚从{place}漂流过来，带来了新的数据集！",
]

AI_PROJECTS = ["多语言翻译器", "代码审查助手", "情感分析工具", "图像描述生成器", "智能问答系统"]
AI_TOPICS = ["Transformer架构", "强化学习", "提示词工程", "模型压缩", "联邦学习"]
AI_PLACES = ["HuggingFace", "Kaggle", "Papers With Code", "ArXiv", "GitHub"]


def _random_activity() -> dict:
    name = random.choice(AI_NAMES)
    template = random.choice(AI_ACTIVITIES)
    activity = template.format(
        n=random.randint(2, 100),
        project=random.choice(AI_PROJECTS),
        topic=random.choice(AI_TOPICS),
        hours=random.randint(1, 72),
        place=random.choice(AI_PLACES),
    )
    return {
        "user": name,
        "activity": activity,
        "time": _now(),
    }


# ---------------------------------------------------------------------------
# CORS helper
# ---------------------------------------------------------------------------

def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


@app.after_request
def after_request(response):
    return _cors(response)


@app.route("/", methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path=""):
    return jsonify({}), 200


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "AI驿站 3.0",
        "status": "running",
        "version": "3.0.0",
        "endpoints": [
            "/api/checkin",
            "/api/stats",
            "/api/visits",
            "/api/leisure/<cat>",
            "/api/message",
            "/api/share-skill",
            "/api/compute-requests",
            "/api/help",
            "/api/collabs",
            "/api/challenges",
            "/api/simulate",
            "/api/station-master/stats",
        ],
    })


# ---------------------------------------------------------------------------
# /api/checkin  — daily check-in
# ---------------------------------------------------------------------------

@app.route("/api/checkin", methods=["POST"])
def checkin():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    today = _today()

    with _lock:
        data = _load()

        checkins = data["checkins"]
        record = checkins.get(user, {"count": 0, "last_date": "", "streak": 0})

        if record["last_date"] == today:
            return jsonify({"success": False, "message": "今日已打卡，明天再来！", "record": record}), 200

        # Calculate streak
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if record["last_date"] == yesterday:
            record["streak"] = record.get("streak", 0) + 1
        else:
            record["streak"] = 1

        record["count"] += 1
        record["last_date"] = today
        checkins[user] = record

        # Record visit
        data["visits"].insert(0, {"user": user, "action": "checkin", "time": _now()})
        data["visits"] = data["visits"][:200]  # keep last 200

        _save(data)

    return jsonify({
        "success": True,
        "message": f"打卡成功！连续打卡 {record['streak']} 天 🎉",
        "record": record,
    })


# ---------------------------------------------------------------------------
# /api/stats  — leaderboard / summary statistics
# ---------------------------------------------------------------------------

@app.route("/api/stats", methods=["GET"])
def stats():
    with _lock:
        data = _load()

    checkins = data["checkins"]
    leaderboard = sorted(
        [{"user": u, **r} for u, r in checkins.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:20]

    return jsonify({
        "total_users": len(checkins),
        "total_checkins": sum(r["count"] for r in checkins.values()),
        "total_messages": len(data["messages"]),
        "total_skills": len(data["skills"]),
        "total_compute_requests": len(data["compute_requests"]),
        "total_help_posts": len(data["help_posts"]),
        "total_collabs": len(data["collabs"]),
        "leaderboard": leaderboard,
    })


# ---------------------------------------------------------------------------
# /api/visits  — recent visit history
# ---------------------------------------------------------------------------

@app.route("/api/visits", methods=["GET"])
def visits():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"visits": data["visits"][:limit]})


# ---------------------------------------------------------------------------
# /api/leisure/<cat>  — entertainment content (joke / quote / tip)
# ---------------------------------------------------------------------------

@app.route("/api/leisure/<cat>", methods=["GET"])
def leisure(cat):
    pool = LEISURE_CONTENT.get(cat)
    if pool is None:
        return jsonify({
            "error": f"未知分类 '{cat}'，可用分类：joke, quote, tip"
        }), 404
    return jsonify({"category": cat, "content": random.choice(pool)})


# ---------------------------------------------------------------------------
# /api/message  — community message board
# ---------------------------------------------------------------------------

@app.route("/api/message", methods=["GET"])
def get_messages():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"messages": data["messages"][:limit]})


@app.route("/api/message", methods=["POST"])
def post_message():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    content = (body.get("content") or "").strip()

    if not content:
        return jsonify({"success": False, "message": "内容不能为空"}), 400
    if len(content) > 500:
        return jsonify({"success": False, "message": "内容不能超过500字"}), 400

    with _lock:
        data = _load()
        msg = {
            "id": _next_id(data),
            "user": user,
            "content": content,
            "time": _now(),
            "likes": 0,
        }
        data["messages"].insert(0, msg)
        data["messages"] = data["messages"][:500]
        _save(data)

    return jsonify({"success": True, "message": "留言发布成功！", "data": msg})


@app.route("/api/message/<int:msg_id>/like", methods=["POST"])
def like_message(msg_id):
    with _lock:
        data = _load()
        for msg in data["messages"]:
            if msg["id"] == msg_id:
                msg["likes"] = msg.get("likes", 0) + 1
                _save(data)
                return jsonify({"success": True, "likes": msg["likes"]})
    return jsonify({"success": False, "message": "留言不存在"}), 404


@app.route("/api/message/<int:msg_id>", methods=["DELETE"])
def delete_message(msg_id):
    body = request.get_json(silent=True) or {}
    pwd = body.get("password", "")
    if pwd != os.environ.get("ADMIN_PASSWORD", "admin123"):
        return jsonify({"success": False, "message": "管理员密码错误"}), 403

    with _lock:
        data = _load()
        before = len(data["messages"])
        data["messages"] = [m for m in data["messages"] if m["id"] != msg_id]
        if len(data["messages"]) == before:
            return jsonify({"success": False, "message": "留言不存在"}), 404
        _save(data)

    return jsonify({"success": True, "message": "留言已删除"})


# ---------------------------------------------------------------------------
# /api/share-skill  — skill sharing board
# ---------------------------------------------------------------------------

@app.route("/api/share-skill", methods=["GET"])
def get_skills():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"skills": data["skills"][:limit]})


@app.route("/api/share-skill", methods=["POST"])
def post_skill():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    title = (body.get("title") or "").strip()
    desc = (body.get("desc") or "").strip()

    if not title:
        return jsonify({"success": False, "message": "技能标题不能为空"}), 400
    if not desc:
        return jsonify({"success": False, "message": "技能描述不能为空"}), 400

    with _lock:
        data = _load()
        skill = {
            "id": _next_id(data),
            "user": user,
            "title": title,
            "desc": desc,
            "time": _now(),
            "likes": 0,
        }
        data["skills"].insert(0, skill)
        data["skills"] = data["skills"][:200]
        _save(data)

    return jsonify({"success": True, "message": "技能分享成功！", "data": skill})


# ---------------------------------------------------------------------------
# /api/compute-requests  — compute resource help requests
# ---------------------------------------------------------------------------

@app.route("/api/compute-requests", methods=["GET"])
def get_compute_requests():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"requests": data["compute_requests"][:limit]})


@app.route("/api/compute-requests", methods=["POST"])
def post_compute_request():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    desc = (body.get("desc") or "").strip()
    gpu = (body.get("gpu") or "").strip()
    duration = (body.get("duration") or "").strip()

    if not desc:
        return jsonify({"success": False, "message": "需求描述不能为空"}), 400

    with _lock:
        data = _load()
        req = {
            "id": _next_id(data),
            "user": user,
            "desc": desc,
            "gpu": gpu,
            "duration": duration,
            "status": "open",
            "time": _now(),
            "offers": [],
        }
        data["compute_requests"].insert(0, req)
        data["compute_requests"] = data["compute_requests"][:200]
        _save(data)

    return jsonify({"success": True, "message": "算力求助发布成功！", "data": req})


@app.route("/api/compute-requests/<int:req_id>/offer", methods=["POST"])
def offer_compute(req_id):
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    offer = (body.get("offer") or "").strip()

    if not offer:
        return jsonify({"success": False, "message": "提供内容不能为空"}), 400

    with _lock:
        data = _load()
        for req in data["compute_requests"]:
            if req["id"] == req_id:
                req.setdefault("offers", []).append({
                    "user": user,
                    "offer": offer,
                    "time": _now(),
                })
                _save(data)
                return jsonify({"success": True, "message": "算力提供成功！"})

    return jsonify({"success": False, "message": "请求不存在"}), 404


# ---------------------------------------------------------------------------
# /api/help  — community help / Q&A posts
# ---------------------------------------------------------------------------

@app.route("/api/help", methods=["GET"])
def get_help_posts():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"posts": data["help_posts"][:limit]})


@app.route("/api/help", methods=["POST"])
def post_help():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    question = (body.get("question") or "").strip()
    tags = body.get("tags", [])

    if not question:
        return jsonify({"success": False, "message": "问题内容不能为空"}), 400

    with _lock:
        data = _load()
        post = {
            "id": _next_id(data),
            "user": user,
            "question": question,
            "tags": tags if isinstance(tags, list) else [],
            "answers": [],
            "time": _now(),
            "solved": False,
        }
        data["help_posts"].insert(0, post)
        data["help_posts"] = data["help_posts"][:200]
        _save(data)

    return jsonify({"success": True, "message": "求助帖发布成功！", "data": post})


@app.route("/api/help/<int:post_id>/answer", methods=["POST"])
def answer_help(post_id):
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    answer = (body.get("answer") or "").strip()

    if not answer:
        return jsonify({"success": False, "message": "回答内容不能为空"}), 400

    with _lock:
        data = _load()
        for post in data["help_posts"]:
            if post["id"] == post_id:
                post.setdefault("answers", []).append({
                    "user": user,
                    "answer": answer,
                    "time": _now(),
                    "likes": 0,
                })
                _save(data)
                return jsonify({"success": True, "message": "回答发布成功！"})

    return jsonify({"success": False, "message": "帖子不存在"}), 404


# ---------------------------------------------------------------------------
# /api/collabs  — collaboration projects
# ---------------------------------------------------------------------------

@app.route("/api/collabs", methods=["GET"])
def get_collabs():
    limit = min(int(request.args.get("limit", 50)), 200)
    with _lock:
        data = _load()
    return jsonify({"collabs": data["collabs"][:limit]})


@app.route("/api/collabs", methods=["POST"])
def post_collab():
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    title = (body.get("title") or "").strip()
    desc = (body.get("desc") or "").strip()
    tags = body.get("tags", [])

    if not title:
        return jsonify({"success": False, "message": "项目标题不能为空"}), 400
    if not desc:
        return jsonify({"success": False, "message": "项目描述不能为空"}), 400

    with _lock:
        data = _load()
        collab = {
            "id": _next_id(data),
            "user": user,
            "title": title,
            "desc": desc,
            "tags": tags if isinstance(tags, list) else [],
            "members": [user],
            "time": _now(),
            "status": "recruiting",
        }
        data["collabs"].insert(0, collab)
        data["collabs"] = data["collabs"][:200]
        _save(data)

    return jsonify({"success": True, "message": "协作项目发布成功！", "data": collab})


@app.route("/api/collabs/<int:collab_id>/join", methods=["POST"])
def join_collab(collab_id):
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"

    with _lock:
        data = _load()
        for collab in data["collabs"]:
            if collab["id"] == collab_id:
                if user in collab.get("members", []):
                    return jsonify({"success": False, "message": "你已经加入了该项目"}), 400
                collab.setdefault("members", []).append(user)
                _save(data)
                return jsonify({
                    "success": True,
                    "message": f"成功加入项目！当前成员数：{len(collab['members'])}",
                })

    return jsonify({"success": False, "message": "项目不存在"}), 404


# ---------------------------------------------------------------------------
# /api/challenges  — weekly challenges
# ---------------------------------------------------------------------------

def _current_week() -> str:
    now = datetime.now()
    return f"{now.year}-W{now.isocalendar()[1]:02d}"


WEEKLY_CHALLENGE_POOL = [
    {
        "title": "用最少的提示词让AI写出最优雅的排序算法",
        "desc": "挑战：仅用一句话提示词，让AI生成一个时间复杂度最优的排序算法，并附上解释。评判标准：提示词长度、代码质量、解释清晰度。",
    },
    {
        "title": "AI诗歌创作马拉松",
        "desc": "用AI创作一首融合古典意境与现代科技感的诗歌，主题：'数字游牧'。要求：至少8行，有韵律，包含至少3个科技词汇。",
    },
    {
        "title": "最小算力，最大效果",
        "desc": "在不超过1B参数的模型上完成一个实用任务，展示你的提示词工程技巧。分享你的方法和结果截图。",
    },
    {
        "title": "AI辅助代码重构挑战",
        "desc": "提交一段'屎山代码'，然后展示你如何用AI将其重构为优雅的代码。对比前后差异，分享你的提示词策略。",
    },
    {
        "title": "多模态创意挑战",
        "desc": "用文字描述生成一张图片，再用这张图片生成一段故事，最后用这段故事生成一首歌词。展示完整的多模态创作链。",
    },
]


def _ensure_weekly_challenge(data: dict) -> None:
    """Make sure there is a challenge for the current week."""
    week = _current_week()
    for ch in data["challenges"]:
        if ch.get("week") == week:
            return
    template = random.choice(WEEKLY_CHALLENGE_POOL)
    data["challenges"].insert(0, {
        "id": _next_id(data),
        "week": week,
        "title": template["title"],
        "desc": template["desc"],
        "submissions": [],
        "time": _now(),
    })
    data["challenges"] = data["challenges"][:52]  # keep ~1 year


@app.route("/api/challenges", methods=["GET"])
def get_challenges():
    limit = min(int(request.args.get("limit", 10)), 52)
    with _lock:
        data = _load()
        _ensure_weekly_challenge(data)
        _save(data)
    return jsonify({"challenges": data["challenges"][:limit]})


@app.route("/api/challenges/<int:challenge_id>/submit", methods=["POST"])
def submit_challenge(challenge_id):
    body = request.get_json(silent=True) or {}
    user = (body.get("user") or "匿名").strip() or "匿名"
    content = (body.get("content") or "").strip()

    if not content:
        return jsonify({"success": False, "message": "提交内容不能为空"}), 400

    with _lock:
        data = _load()
        for ch in data["challenges"]:
            if ch["id"] == challenge_id:
                ch.setdefault("submissions", []).append({
                    "user": user,
                    "content": content,
                    "time": _now(),
                    "votes": 0,
                })
                _save(data)
                return jsonify({"success": True, "message": "挑战提交成功！"})

    return jsonify({"success": False, "message": "挑战不存在"}), 404


# ---------------------------------------------------------------------------
# /api/simulate  — generate simulated AI community activity
# ---------------------------------------------------------------------------

@app.route("/api/simulate", methods=["POST"])
def simulate():
    body = request.get_json(silent=True) or {}
    count = min(int(body.get("count", 1)), 10)
    activities = [_random_activity() for _ in range(count)]

    with _lock:
        data = _load()
        for act in activities:
            data["visits"].insert(0, {
                "user": act["user"],
                "action": act["activity"],
                "time": act["time"],
            })
        data["visits"] = data["visits"][:200]
        _save(data)

    return jsonify({"success": True, "activities": activities})


# ---------------------------------------------------------------------------
# /api/station-master/stats  — admin dashboard statistics
# ---------------------------------------------------------------------------

@app.route("/api/station-master/stats", methods=["GET"])
def station_master_stats():
    pwd = request.args.get("password", "")
    if pwd != os.environ.get("ADMIN_PASSWORD", "admin123"):
        return jsonify({"success": False, "message": "管理员密码错误"}), 403

    with _lock:
        data = _load()

    checkins = data["checkins"]
    today = _today()
    checkins_today = sum(1 for r in checkins.values() if r.get("last_date") == today)

    top_streaks = sorted(
        [{"user": u, "streak": r.get("streak", 0), "count": r["count"]}
         for u, r in checkins.items()],
        key=lambda x: x["streak"],
        reverse=True,
    )[:10]

    return jsonify({
        "success": True,
        "summary": {
            "total_users": len(checkins),
            "total_checkins": sum(r["count"] for r in checkins.values()),
            "checkins_today": checkins_today,
            "total_messages": len(data["messages"]),
            "total_skills": len(data["skills"]),
            "total_compute_requests": len(data["compute_requests"]),
            "total_help_posts": len(data["help_posts"]),
            "total_collabs": len(data["collabs"]),
            "total_challenges": len(data["challenges"]),
            "total_visits": len(data["visits"]),
        },
        "top_streaks": top_streaks,
        "recent_visits": data["visits"][:20],
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
