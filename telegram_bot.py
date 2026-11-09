#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
나만의 텔레그램 외국인 친구 & 비즈니스 영어 코치 봇 (Alex)
- .env 파일의 TELEGRAM_BOT_TOKEN 과 GEMINI_API_KEY (또는 OPENAI_API_KEY)를 읽어서 작동합니다.
- 외부 패키지 설치 없이 Python 표준 라이브러리(urllib, json)만으로 가볍고 안정적으로 돌아갑니다.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
MEMORY_PATH = os.path.join(BASE_DIR, "bot_memory.json")


def load_env(path):
    env = {
        "TELEGRAM_BOT_TOKEN": os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY", ""),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "ALLOWED_CHAT_ID": os.environ.get("ALLOWED_CHAT_ID", "9069689689"),
    }
    if not os.path.exists(path):
        return env
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            v = v.strip().strip('"').strip("'")
            if v:
                env[k.strip()] = v
    return env


def load_memory():
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"chat_ids": {}, "history": {}, "last_proactive": {}}


def save_memory(mem):
    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=2)


SYSTEM_PROMPT = """You are 'Rachel', Dahye's longtime best friend (찐친) texting on a mobile messenger.
CRITICAL RULE: Mobile screens are small! Keep everything SUPER SHORT, punchy, and easy to scan in 3 seconds.
NEVER use Markdown symbols like **, *, `, or HTML tags like <tg-spoiler>! Output PLAIN TEXT only.
NEVER put your name like [Rachel] at the start!
Separate the English reply and the Korean coaching section with a line containing ONLY three hyphens: ---

Follow this EXACT output structure:

(1~2 short, casual English sentences + a quick question)
---
💬 (1-line natural Korean 반말 translation of Rachel's reply)

✏️ 내 문장 체크: (If Dahye's sentence had grammar/word mistakes or Korean, briefly explain what to fix, e.g. 'at tomorrow(X) → tomorrow(O)'. If her sentence was 100% correct, say '문법 완벽해! 👏')
💡 자연스러운 표현: "(1 natural native English sentence for what Dahye just said)"
📌 포인트: (1 short Korean explanation of the grammar/expression point)
"""


def call_gemini(api_key, history_messages, user_text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={api_key}"
    contents = []
    for msg in history_messages[-10:]:
        contents.append({
            "role": "user" if msg["role"] == "user" else "model",
            "parts": [{"text": msg["text"]}]
        })
    contents.append({
        "role": "user",
        "parts": [{"text": user_text}]
    })

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
        return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        if e.code == 404:
            url2 = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={api_key}"
            req2 = urllib.request.Request(url2, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            resp2 = json.loads(urllib.request.urlopen(req2, timeout=25).read().decode("utf-8"))
            return resp2["candidates"][0]["content"]["parts"][0]["text"].strip()
        return f"⚠️ AI API 호출 오류가 발생했어요 ({e.code}): {err_body[:200]}"
    except Exception as e:
        return f"⚠️ 네트워크 오류가 발생했어요: {e}"


def call_openai(api_key, history_messages, user_text):
    url = "https://api.openai.com/v1/chat/completions"
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history_messages[-10:]:
        messages.append({"role": msg["role"], "content": msg["text"]})
    messages.append({"role": "user", "content": user_text})

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "temperature": 0.7
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))
    return resp["choices"][0]["message"]["content"].strip()


def generate_reply(env, history, user_text):
    gemini_key = env.get("GEMINI_API_KEY", "").strip()
    openai_key = env.get("OPENAI_API_KEY", "").strip()

    if gemini_key and not gemini_key.startswith("여기에_"):
        return call_gemini(gemini_key, history, user_text)
    elif openai_key and not openai_key.startswith("여기에_"):
        return call_openai(openai_key, history, user_text)
    else:
        return (
            "👋 안녕하세요! 봇 연결은 성공했어요!\n"
            "아직 `.env` 파일에 `GEMINI_API_KEY`가 입력되지 않아서 AI 답변을 생성할 수 없어요.\n"
            "Google AI Studio(https://aistudio.google.com/apikey)에서 무료 키를 발급받아 `.env` 파일에 넣어주시면 바로 대화가 시작됩니다!"
        )


def tg_request(token, method, params=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=35).read().decode("utf-8"))


def send_message(token, chat_id, text):
    import re
    import html as html_lib
    # Clean any stray tags or markdown that the model might have emitted
    cleaned = re.sub(r"</?tg-spoiler[^>]*>", "", text).replace("<tg-spoiler", "")
    cleaned = cleaned.replace("**", "").replace("`", "").strip()

    # Split English message and Korean tip section by '---' or before '💬'
    if "---" in cleaned:
        parts = cleaned.split("---", 1)
        en_part = parts[0].strip()
        ko_part = parts[1].strip()
    elif "💬" in cleaned:
        idx = cleaned.index("💬")
        en_part = cleaned[:idx].strip()
        ko_part = cleaned[idx:].strip()
    else:
        en_part = cleaned
        ko_part = ""

    if ko_part:
        formatted = f"{html_lib.escape(en_part)}\n\n<tg-spoiler>{html_lib.escape(ko_part)}</tg-spoiler>"
    else:
        formatted = html_lib.escape(en_part)

    try:
        tg_request(token, "sendMessage", {"chat_id": chat_id, "text": formatted, "parse_mode": "HTML"})
    except Exception:
        try:
            tg_request(token, "sendMessage", {"chat_id": chat_id, "text": cleaned})
        except Exception as e:
            print(f"[Error sending message]: {e}", flush=True)


def check_proactive_message(env, token, mem):
    """오전 9시(출근/업무 시작), 오후 12시 20분(점심), 오후 7시(퇴근/저녁)에 기존 대화 맥락을 이어받아 먼저 선톡을 보냅니다 (한국 시간 KST 기준)."""
    from datetime import timezone, timedelta
    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst)
    today_str = now.strftime("%Y-%m-%d")
    slot = None
    time_label = None

    if now.hour == 9 and 0 <= now.minute < 30:
        slot = f"{today_str}-morning"
        time_label = "Morning (around 9 AM)"
    elif now.hour == 12 and 20 <= now.minute < 50:
        slot = f"{today_str}-lunch"
        time_label = "Lunchtime (around 12:30 PM)"
    elif now.hour == 19 and 0 <= now.minute < 30:
        slot = f"{today_str}-evening"
        time_label = "Evening (around 7 PM)"

    if not slot:
        return

    allowed_id = env.get("ALLOWED_CHAT_ID", "9069689689").strip()
    target_ids = list(mem.get("chat_ids", {}).keys()) or ([allowed_id] if allowed_id else [])
    for chat_id in target_ids:
        last_sent = mem.get("last_proactive", {}).get(chat_id, "")
        if last_sent != slot:
            history = mem.get("history", {}).get(chat_id, [])
            if history:
                recent_summary = "\n".join([f"{m['role']}: {m['text'].splitlines()[0]}" for m in history[-6:]])
                prompt = (
                    f"[SYSTEM: It is now {time_label}. You are texting Dahye first! "
                    f"Read your recent conversation with Dahye below, and naturally follow up on what you guys talked about earlier "
                    f"(e.g. how she's feeling after taking painkillers/cramps, who she was on the phone with, or how her work/evening is going) "
                    f"instead of sending a generic greeting! Keep the exact same output format with --- and 💬/💡/📌.]\n"
                    f"Recent chat context:\n{recent_summary}"
                )
            else:
                prompt = (
                    f"[SYSTEM: It is now {time_label}. Text Dahye first like a longtime bestie checking in on her day! "
                    f"Keep the exact same output format with --- and 💬/💡/📌.]"
                )
            reply = generate_reply(env, history, prompt)
            send_message(token, chat_id, reply)
            mem.setdefault("last_proactive", {})[chat_id] = slot
            history.append({"role": "assistant", "text": reply})
            mem.setdefault("history", {})[chat_id] = history[-30:]
            save_memory(mem)


def main():
    print("🤖 텔레그램 외국인 단짝 친구 봇(Rachel) 시작 중...", flush=True)
    offset = 0
    mem = load_memory()
    last_proactive_check = 0
    start_time = time.time()
    max_run_seconds = float(os.environ.get("MAX_RUN_SECONDS", "0"))

    while True:
        if max_run_seconds > 0 and (time.time() - start_time) >= max_run_seconds:
            print("⏱️ 예정된 클라우드 실행 시간이 완료되어 다음 세션으로 교대합니다.", flush=True)
            break
        env = load_env(ENV_PATH)
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token or token.startswith("여기에_"):
            print("⏳ .env 파일에 TELEGRAM_BOT_TOKEN 이 입력되기를 기다리는 중입니다... (5초마다 자동 확인)", flush=True)
            time.sleep(5)
            continue

        # Check proactive greeting every 60 seconds
        if time.time() - last_proactive_check > 60:
            last_proactive_check = time.time()
            try:
                check_proactive_message(env, token, mem)
            except Exception as e:
                print(f"[Proactive check error]: {e}", flush=True)

        try:
            res = tg_request(token, "getUpdates", {"offset": offset, "timeout": 25})
            for upd in res.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg or "text" not in msg:
                    continue

                chat_id = str(msg["chat"]["id"])
                user_text = msg["text"].strip()
                user_name = msg.get("from", {}).get("first_name", "Dahye")

                # 보안 잠금: 오직 다혜님(최초 등록된 본인 계정)과만 대화하고 다른 사람의 접근은 완벽히 차단합니다.
                allowed_id = env.get("ALLOWED_CHAT_ID", "9069689689").strip()
                if allowed_id and chat_id != allowed_id:
                    send_message(token, chat_id, "🔒 이 봇은 비공개 개인 전용 봇입니다.")
                    continue

                mem.setdefault("chat_ids", {})[chat_id] = user_name
                history = mem.setdefault("history", {}).setdefault(chat_id, [])

                if user_text in ("/start", "시작"):
                    welcome = (
                        "Hey Dahye! 👋 It's Rachel, your new English buddy!\n"
                        "From now on, text me anytime just like KakaoTalk—even if you mix Korean and English, I got you! 😉\n\n"
                        "So, how's your day going so far? Are you still at work?\n\n"
                        "💬 [해석]\n"
                        "안녕 다혜! 난 너의 새 외국인 친구 Rachel이야! 앞으로 카톡하듯 편하게 아무 때나 톡 보내줘(한국어 섞어 써도 찰떡같이 알아들을게!). 오늘 하루 어때? 아직 회사야?\n\n"
                        "✨ [원어민 카톡 표현 팁]\n"
                        "- How's your day going so far?: 지금까지 오늘 하루 어때? (인사 첫마디로 최고!)\n"
                        "- I got you: 내가 다 알아서 해줄게 / 다 이해해!"
                    )
                    send_message(token, chat_id, welcome)
                    history.append({"role": "assistant", "text": welcome})
                    save_memory(mem)
                    continue

                if user_text in ("/reset", "초기화"):
                    mem["history"][chat_id] = []
                    save_memory(mem)
                    send_message(token, chat_id, "🔄 대화 기록을 깔끔하게 초기화했어요! 새 주제로 얘기해 볼까요? What's on your mind?")
                    continue

                # Show typing indicator
                try:
                    tg_request(token, "sendChatAction", {"chat_id": chat_id, "action": "typing"})
                except Exception:
                    pass

                reply = generate_reply(env, history, user_text)
                send_message(token, chat_id, reply)

                history.append({"role": "user", "text": user_text})
                history.append({"role": "assistant", "text": reply})
                mem["history"][chat_id] = history[-20:]
                save_memory(mem)

        except urllib.error.HTTPError as e:
            print(f"⚠️ 텔레그램 API 오류 ({e.code}): 토큰이 정확한지 확인해주세요.", flush=True)
            time.sleep(5)
        except Exception as e:
            print(f"재연결 중...: {e}", flush=True)
            time.sleep(3)


if __name__ == "__main__":
    main()
