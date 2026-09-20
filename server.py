# server.py — онлайн MOBA 3v3

import asyncio
import json
import os
import random
import time
import websockets
from shared import HEROES


SAVE_FILE = "save.json"

# ═══════════════════════════════════════════════
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ═══════════════════════════════════════════════

players = {}      # {nick: {password, friends: [], wins, losses, hero: "vermil"}}
online = {}       # {ws: nick}
chat_gc = []      # общий чат: [(ник, текст), ...]
chat_tc = {}      # тим-чаты: {match_id: [(ник, текст), ...]}
lobbies = {}      # {lobby_id: {"players": [ник, ...], "host": ник, "ready": {ник: bool}, "size": 3, "mode": "3v3"}}
matches = {}      # {match_id: {"lobby": ..., "state": {...}}}
player_match = {} # {ник: match_id} — в какой игре сейчас


def save_data():
    data = {"players": players}
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_data():
    global players
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            players = data.get("players", {})
        except Exception as e:
            print(f"[СЕРВЕР] Ошибка загрузки: {e}")


def now():
    return time.time()


def new_player(nick):
    return {
        "password": "",
        "friends": [],
        "hero": "vermil",
        "wins": 0,
        "losses": 0,
    }


# ═══════════════════════════════════════════════
# ОТПРАВКА
# ═══════════════════════════════════════════════

async def send(ws, msg):
    try:
        await ws.send(json.dumps(msg, ensure_ascii=False))
    except Exception:
        pass


async def send_to_nick(nick, msg):
    for w, n in list(online.items()):
        if n == nick:
            await send(w, msg)


async def broadcast(msg, exclude=None):
    for w, n in list(online.items()):
        if n != exclude:
            await send(w, msg)


# ═══════════════════════════════════════════════
# ЛОББИ
# ═══════════════════════════════════════════════

def lobby_list():
    result = []
    for lid, l in lobbies.items():
        result.append({
            "id": lid,
            "host": l["host"],
            "players": l["players"],
            "size": l["size"],
            "count": len(l["players"]),
        })
    return result


async def lobby_broadcast():
    await broadcast({"type": "lobby_list", "lobbies": lobby_list()})


# ═══════════════════════════════════════════════
# СОЗДАНИЕ ЮНИТА
# ═══════════════════════════════════════════════

def make_unit(nick, hero_key, team):
    base = HEROES[hero_key]
    return {
        "nick": nick,
        "hero": hero_key,
        "name": base["name"],
        "team": team,
        "is_player": True,   # все игроки
        "hp": base["hp"], "max_hp": base["hp"],
        "mp": base["mp"], "max_mp": base["mp"],
        "dmg": base["dmg"],
        "skills": {k: dict(v) for k, v in base["skills"].items()},
        "line": "start",
        "cd": {"1": 0, "2": 0, "3": 0},
        "stunned_until": 0,
        "alive": True,
        "running": False,
        "respawn_at": 0,
    }


def make_tower(team, line):
    return {
        "team": team, "line": line,
        "hp": 2000, "max_hp": 2000, "dmg": 100,
        "alive": True, "last_hit": 0,
    }


def make_match_state(blue_nicks, red_nicks):
    blue_units = [make_unit(n, players[n]["hero"], "blue") for n in blue_nicks]
    red_units = [make_unit(n, players[n]["hero"], "red") for n in red_nicks]
    
    lines = ["mid", "up", "down"]
    for i, u in enumerate(blue_units):
        u["line"] = lines[i % 3]
    for i, u in enumerate(red_units):
        u["line"] = lines[i % 3]
    
    towers = []
    for line in lines:
        towers.append(make_tower("blue", line))
        towers.append(make_tower("red", line))
    
    return {
        "units": blue_units + red_units,
        "towers": towers,
        "blue": blue_nicks,
        "red": red_nicks,
        "started": now(),
        "finished": False,
        "winner": None,
        "last_tick": now(),
    }


# ═══════════════════════════════════════════════
# БОЙ
# ═══════════════════════════════════════════════

def attack(attacker, target):
    dmg = attacker["dmg"] + random.randint(-10, 10)
    target["hp"] -= dmg
    if target["hp"] < 0:
        target["hp"] = 0
    return f"{attacker['name']} → {target['name']}: -{dmg} HP ({target['hp']}/{target['max_hp']})"


def cast_skill(attacker, target, skill_key):
    skill = attacker["skills"][skill_key]
    
    if attacker["mp"] < skill["mp"]:
        return None
    if attacker["cd"][skill_key] > now():
        return None
    
    attacker["mp"] -= skill["mp"]
    attacker["cd"][skill_key] = now() + skill["cd"]
    
    dmg = skill["dmg"] + random.randint(-15, 15)
    target["hp"] -= dmg
    if target["hp"] < 0:
        target["hp"] = 0
    
    text = f"⚡ {attacker['name']} {skill['name']} → {target['name']}: -{dmg} HP ({target['hp']}/{target['max_hp']})"
    if "stun" in skill:
        target["stunned_until"] = now() + skill["stun"]
        text += f" [стан {skill['stun']}с]"
    return text


def check_death(unit):
    if unit["hp"] <= 0 and unit["alive"]:
        unit["alive"] = False
        unit["respawn_at"] = now() + 10
        return f"💀 {unit['name']} погиб"
    return None


def respawn_check(match):
    for u in match["units"]:
        if not u["alive"] and u["respawn_at"] > 0 and now() >= u["respawn_at"]:
            u["alive"] = True
            u["hp"] = u["max_hp"]
            u["mp"] = u["max_mp"]
            u["line"] = "start"
            u["respawn_at"] = 0
            u["stunned_until"] = 0
            u["cd"] = {"1": 0, "2": 0, "3": 0}


def ai_turn(npc, all_units):
    events = []
    if npc["stunned_until"] > now():
        return events
    
    enemy_team = "blue" if npc["team"] == "red" else "red"
    enemies_here = [u for u in all_units if u["alive"] and u["line"] == npc["line"] and u["team"] == enemy_team]
    if not enemies_here:
        return events
    
    target = min(enemies_here, key=lambda u: u["hp"])
    
    if npc["hp"] < npc["max_hp"] * 0.2:
        npc["running"] = True
        events.append(f"🏃 {npc['name']} убегает")
        return events
    
    if random.random() < 0.5:
        r = cast_skill(npc, target, random.choice(["1", "2", "3"]))
        if r:
            events.append(r)
    else:
        events.append(attack(npc, target))
    
    d = check_death(target)
    if d:
        events.append(d)
    return events


async def match_tick(match_id):
    """Каждые 3 секунды — ход ботов (если игроков меньше 3)."""
    while match_id in matches:
        await asyncio.sleep(3)
        match = matches.get(match_id)
        if not match or match["finished"]:
            break
        
        respawn_check(match)
        
        # боты-союзники и враги (если <3 живых игроков)
        # пока упрощённо — не добавляем ботов, ждём игроков
        
        # башни
        for t in match["towers"]:
            if not t["alive"]:
                continue
            if now() - t["last_hit"] < 2:
                continue
            enemy_team = "red" if t["team"] == "blue" else "blue"
            targets = [u for u in match["units"] if u["alive"] and u["line"] == t["line"] and u["team"] == enemy_team]
            if not targets:
                continue
            target = targets[0]
            target["hp"] -= t["dmg"]
            if target["hp"] < 0:
                target["hp"] = 0
            t["last_hit"] = now()
            d = check_death(target)
            if d:
                await broadcast_in_match(match_id, {"type": "log", "text": d})
        
        # победа
        blue_alive = any(u["alive"] or u["respawn_at"] > 0 for u in match["units"] if u["team"] == "blue")
        red_alive = any(u["alive"] or u["respawn_at"] > 0 for u in match["units"] if u["team"] == "red")
        
        if not red_alive:
            match["finished"] = True
            match["winner"] = "blue"
            await broadcast_in_match(match_id, {"type": "match_end", "winner": "blue"})
            # статистика
            for n in match["blue"]:
                if n in players:
                    players[n]["wins"] += 1
            for n in match["red"]:
                if n in players:
                    players[n]["losses"] += 1
            save_data()
            break
        if not blue_alive:
            match["finished"] = True
            match["winner"] = "red"
            await broadcast_in_match(match_id, {"type": "match_end", "winner": "red"})
            for n in match["red"]:
                if n in players:
                    players[n]["wins"] += 1
            for n in match["blue"]:
                if n in players:
                    players[n]["losses"] += 1
            save_data()
            break


async def broadcast_in_match(match_id, msg):
    match = matches.get(match_id)
    if not match:
        return
    for nick in match["blue"] + match["red"]:
        await send_to_nick(nick, msg)


def find_player_unit(match, nick):
    for u in match["units"]:
        if u["nick"] == nick:
            return u
    return None


def enemies_on_line(match, line, my_team):
    enemy_team = "red" if my_team == "blue" else "blue"
    return [u for u in match["units"] if u["alive"] and u["line"] == line and u["team"] == enemy_team]


# ═══════════════════════════════════════════════
# ОБРАБОТКА КОМАНД
# ═══════════════════════════════════════════════

async def handle(ws, nick, data):
    p = players[nick]
    cmd = data.get("cmd")
    match_id = player_match.get(nick)
    
    # ─── ГЛОБАЛЬНЫЙ ЧАТ ───
    if cmd == "gc":
        text = str(data.get("text", ""))[:200]
        if text.strip():
            chat_gc.append((nick, text))
            if len(chat_gc) > 100:
                chat_gc.pop(0)
            await broadcast({"type": "gc", "from": nick, "text": text})
        return
    
    # ─── ТИМ-ЧАТ ───
    if cmd == "tc":
        if not match_id:
            await send(ws, {"type": "error", "text": "Ты не в игре"})
            return
        text = str(data.get("text", ""))[:200]
        if text.strip():
            chat_tc.setdefault(match_id, []).append((nick, text))
            match = matches[match_id]
            my_team = "blue" if nick in match["blue"] else "red"
            for n in (match["blue"] if my_team == "blue" else match["red"]):
                await send_to_nick(n, {"type": "tc", "from": nick, "text": text})
        return
    
    # ─── ЛИЧКА ───
    if cmd == "pm":
        target = data.get("to")
        text = str(data.get("text", ""))[:200]
        if target not in players:
            await send(ws, {"type": "error", "text": "Нет такого игрока"})
            return
        await send_to_nick(target, {"type": "pm", "from": nick, "text": text})
        await send(ws, {"type": "pm", "from": nick, "text": text})
        return
    
    # ─── ДРУЗЬЯ ───
    if cmd == "friend_add":
        target = data.get("nick")
        if target not in players:
            await send(ws, {"type": "error", "text": "Нет такого"})
            return
        if target in p["friends"]:
            await send(ws, {"type": "error", "text": "Уже в друзьях"})
            return
        p["friends"].append(target)
        save_data()
        await send(ws, {"type": "info", "text": f"{target} добавлен в друзья"})
        return
    
    if cmd == "friend_del":
        target = data.get("nick")
        if target in p["friends"]:
            p["friends"].remove(target)
            save_data()
            await send(ws, {"type": "info", "text": f"{target} удалён"})
        return
    
    if cmd == "friends":
        result = []
        for f in p["friends"]:
            status = "🟢" if f in online.values() else "⚫"
            result.append(f"{status} {f}")
        await send(ws, {"type": "info", "text": "Друзья:\n" + "\n".join(result) if result else "Нет друзей"})
        return
    
    # ─── ВЫБОР ГЕРОЯ ───
    if cmd == "hero":
        hero = data.get("hero")
        if hero in HEROES:
            p["hero"] = hero
            save_data()
            await send(ws, {"type": "info", "text": f"Герой: {HEROES[hero]['name']}"})
        return
    
    # ─── ЛОББИ ───
    if cmd == "lobby_list":
        await send(ws, {"type": "lobby_list", "lobbies": lobby_list()})
        return
    
    if cmd == "lobby_create":
        # выйти из старого
        for lid, l in list(lobbies.items()):
            if nick in l["players"]:
                l["players"].remove(nick)
                if not l["players"]:
                    del lobbies[lid]
        
        lid = str(random.randint(1000, 9999))
        lobbies[lid] = {
            "host": nick,
            "players": [nick],
            "ready": {nick: False},
            "size": 3,
        }
        await send(ws, {"type": "info", "text": f"Лобби {lid} создано"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_join":
        lid = str(data.get("id"))
        if lid not in lobbies:
            await send(ws, {"type": "error", "text": "Нет такого лобби"})
            return
        l = lobbies[lid]
        if len(l["players"]) >= l["size"] * 2:
            await send(ws, {"type": "error", "text": "Лобби полно"})
            return
        if nick not in l["players"]:
            l["players"].append(nick)
            l["ready"][nick] = False
        await send(ws, {"type": "info", "text": f"Ты в лобби {lid}"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_leave":
        for lid, l in list(lobbies.items()):
            if nick in l["players"]:
                l["players"].remove(nick)
                l["ready"].pop(nick, None)
                if not l["players"]:
                    del lobbies[lid]
                else:
                    if l["host"] == nick and l["players"]:
                        l["host"] = l["players"][0]
                break
        await send(ws, {"type": "info", "text": "Ты вышел из лобби"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_ready":
        for lid, l in lobbies.items():
            if nick in l["players"]:
                l["ready"][nick] = not l["ready"].get(nick, False)
                await send(ws, {"type": "info", "text": f"Готовность: {l['ready'][nick]}"})
                await lobby_broadcast()
                break
        return
    
    if cmd == "lobby_start":
        lid = None
        for _lid, l in lobbies.items():
            if nick in l["players"]:
                lid = _lid
                break
        if not lid:
            await send(ws, {"type": "error", "text": "Ты не в лобби"})
            return
        l = lobbies[lid]
        if l["host"] != nick:
            await send(ws, {"type": "error", "text": "Ты не хост"})
            return
        if len(l["players"]) < 2:
            await send(ws, {"type": "error", "text": "Нужно минимум 2 игрока"})
            return
        if not all(l["ready"].get(n, False) for n in l["players"]):
            await send(ws, {"type": "error", "text": "Не все готовы"})
            return
        
        # разделяем на команды
        shuffled = l["players"][:]
        random.shuffle(shuffled)
        half = len(shuffled) // 2
        blue = shuffled[:half]
        red = shuffled[half:]
        
        # если нечётное — один игрок идёт в синюю
        if len(shuffled) % 2 == 1:
            blue.append(shuffled[-1])
        
        mid = str(random.randint(10000, 99999))
        matches[mid] = make_match_state(blue, red)
        for n in blue + red:
            player_match[n] = mid
        
        del lobbies[lid]
        
        await broadcast_in_match(mid, {
            "type": "match_start",
            "match_id": mid,
            "blue": blue,
            "red": red,
        })
        await lobby_broadcast()
        
        # запускаем тик
        asyncio.create_task(match_tick(mid))
        return
    
    # ─── ИГРОВЫЕ КОМАНДЫ ───
    if not match_id:
        await send(ws, {"type": "error", "text": "Ты не в игре"})
        return
    
    match = matches.get(match_id)
    if not match or match["finished"]:
        await send(ws, {"type": "error", "text": "Матч окончен"})
        return
    
    unit = find_player_unit(match, nick)
    if not unit:
        return
    
    # ─── ИНФО ───
    if cmd == "st":
        await send(ws, {"type": "state", "data": unit, "match_id": match_id})
        return
    
    if cmd == "go":
        line = data.get("line")
        if line not in ["start", "mid", "up", "down"]:
            return
        unit["line"] = line
        await send(ws, {"type": "log", "text": f"Ты на линии {line}"})
        return
    
    if cmd == "cast":
        if unit["line"] == "start":
            await send(ws, {"type": "log", "text": "На базе нельзя"})
            return
        if unit["stunned_until"] > now():
            await send(ws, {"type": "log", "text": "Ты в стане"})
            return
        
        skill_key = str(data.get("skill"))
        enemies_here = enemies_on_line(match, unit["line"], unit["team"])
        if not enemies_here:
            await send(ws, {"type": "log", "text": "Нет врагов на линии"})
            return
        
        target = enemies_here[0]
        result = cast_skill(unit, target, skill_key)
        if result:
            await send(ws, {"type": "log", "text": result})
            # отправить врагам на линии
            for e in enemies_here:
                await send_to_nick(e["nick"], {"type": "log", "text": result})
            d = check_death(target)
            if d:
                await broadcast_in_match(match_id, {"type": "log", "text": d})
        return
    
    if cmd == "rf":
        if unit["line"] == "start":
            await send(ws, {"type": "log", "text": "Уже на базе"})
            return
        unit["running"] = True
        unit["flee_until"] = now() + 2.2
        await send(ws, {"type": "log", "text": "🏃 Ты убегаешь"})
        return


# ═══════════════════════════════════════════════
# ПОДКЛЮЧЕНИЕ
# ═══════════════════════════════════════════════

async def client_handler(ws, path=None):
    nick = None
    try:
        raw = await ws.recv()
        data = json.loads(raw)
        nick = str(data.get("nick", "")).strip()[:20]
        password = str(data.get("password", ""))[:50]
        
        if not nick:
            await send(ws, {"type": "error", "text": "Пустой ник"})
            return
        
        if nick not in players:
            players[nick] = new_player(nick)
            players[nick]["password"] = password
            await send(ws, {"type": "info", "text": f"Добро пожаловать, {nick}!"})
        else:
            if players[nick]["password"] and players[nick]["password"] != password:
                await send(ws, {"type": "error", "text": "Неверный пароль"})
                return
            await send(ws, {"type": "info", "text": f"С возвращением, {nick}!"})
        
        online[ws] = nick
        print(f"[СЕРВЕР] {nick} онлайн")
        
        await send(ws, {"type": "state_full", "data": players[nick]})
        await send(ws, {"type": "gc_history", "messages": chat_gc[-20:]})
        await lobby_broadcast()
        
        async for raw in ws:
            try:
                data = json.loads(raw)
            except Exception:
                continue
            await handle(ws, nick, data)
    
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"[СЕРВЕР] Ошибка: {e}")
    finally:
        if ws in online:
            del online[ws]
        if nick:
            print(f"[СЕРВЕР] {nick} отключился")
            # выкинуть из лобби
            for lid, l in list(lobbies.items()):
                if nick in l["players"]:
                    l["players"].remove(nick)
                    if not l["players"]:
                        del lobbies[lid]
            await lobby_broadcast()


# ═══════════════════════════════════════════════
# ЗАПУСК
# ═══════════════════════════════════════════════

async def main():
    load_data()
    port = int(os.environ.get("PORT", 8765))
    print(f"[СЕРВЕР] Запуск на порту {port}")
    
    async with websockets.serve(client_handler, "0.0.0.0", port):
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        save_data()
        print("Выход")
