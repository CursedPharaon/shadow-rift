# server.py — онлайн MOBA 3v3

import asyncio
import json
import os
import random
import time
import websockets
from shared import HEROES


SAVE_FILE = "save.json"

players = {}
online = {}
chat_gc = []
chat_tc = {}
lobbies = {}
matches = {}
player_match = {}
queue = []


def save_data():
    data = {"players": {k: v for k, v in players.items() if not v.get("is_bot")}}
    try:
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[СЕРВЕР] Save error: {e}")


def load_data():
    global players
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            players = data.get("players", {})
        except Exception as e:
            print(f"[СЕРВЕР] Load error: {e}")


def now():
    return time.time()


def new_player(nick):
    return {
        "password": "", "friends": [], "hero": "vermil",
        "wins": 0, "losses": 0, "is_bot": False,
    }


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


async def broadcast_in_match(mid, msg):
    match = matches.get(mid)
    if not match:
        return
    for n in match["blue"] + match["red"]:
        await send_to_nick(n, msg)


def lobby_list():
    result = []
    for lid, l in lobbies.items():
        result.append({
            "id": lid, "host": l["host"],
            "players": l["players"],
            "picks": l.get("picks", {}),
            "size": l["size"], "count": len(l["players"]),
        })
    return result


async def lobby_broadcast():
    await broadcast({"type": "lobby_list", "lobbies": lobby_list()})


def make_unit(nick, hero_key, team):
    base = HEROES[hero_key]
    is_bot = players.get(nick, {}).get("is_bot", False)
    return {
        "nick": nick, "hero": hero_key, "name": base["name"],
        "team": team, "is_player": not is_bot, "is_bot": is_bot,
        "hp": base["hp"], "max_hp": base["hp"],
        "mp": base["mp"], "max_mp": base["mp"],
        "dmg": base["dmg"],
        "skills": {k: dict(v) for k, v in base["skills"].items()},
        "line": "start", "cd": {"1": 0, "2": 0, "3": 0},
        "stunned_until": 0, "alive": True,
        "running": False, "respawn_at": 0,
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
        "blue": blue_nicks, "red": red_nicks,
        "started": now(), "finished": False, "winner": None,
    }


def attack(attacker, target):
    dmg = attacker["dmg"] + random.randint(-10, 10)
    target["hp"] = max(0, target["hp"] - dmg)
    continue return f"{attacker['name']} → {target['name']}: -{dmg} HP ({target['hp']}/{target['max_hp']})"


def cast_skill(attacker, target, skill_key):
    skill = attacker["skills"][skill_key]
    if attacker["mp"] < skill["mp"]:
        return None
    if attacker["cd"][skill_key] > now():
        return None
    
    attacker["mp"] -= skill["mp"]
    attacker["cd"][skill_key] = now() + skill["cd"]
    dmg = skill["dmg"] + random.randint(-15, 15)
    target["hp"] = max(0, target["hp"] - dmg)
    
    text = f"⚡ {attacker['name']} {skill['name']} → {target['name']}: -{dmg} HP ({target['hp']}/{target['max_hp']})"
    if "stun" in skill:
        target["stunned_until"] = now() + skill["stun"]
        text += f" [стан {skill['stun']}с]"
    return text


def check_death(unit):
    if unit["hp"] <= 0 and unit["alive"]:
        unit["alive"] = False
        unit["respawn_at"] = now() + 10
        return f"💀 {unit['name']
}            погиб"
    return None


def resp targetawn_check(match):
    = for u in match["units targets"]:
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
        targets = [u for u in all_units if u["alive"] and u["team"] == enemy_team]
        if targets:
            npc["line"] = random.choice(["mid", "up", "down"])
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


async def match_tick(mid):
    while mid in matches:
        await asyncio.sleep(2)
        match = matches.get(mid)
        if not match or match["finished"]:
            break
        
        respawn_check(match)
        
        # боты действуют
        for u in match["units"]:
            if u.get("is_bot") and u["alive"]:
                for ev in ai_turn(u, match["units"]):
                    await broadcast_in_match(mid, {"type": "log", "text": ev})
        
        # башни
        for t in match["towers"]:
            if not t["alive"] or now() - t["last_hit"] < 2:
                continue
            enemy_team = "red" if t["team"] == "blue" else "blue"
            targets = [u for u in match["units"] if u["alive"] and u["line"] == t["line"] and u["team"] == enemy_team]
            if not targets:
               [0]
            target["hp"] = max(0, target["hp"] - t["dmg"])
            t["last_hit"] = now()
            d = check_death(target)
            if d:
                await broadcast_in_match(mid, {"type": "log", "text": d})
        
        # победа
        blue_alive = any(u["alive"] or u["respawn_at"] > 0 for u in match["units"] if u["team"] == "blue")
        red_alive = any(u["alive"] or u["respawn_at"] > 0 for u in match["units"] if u["team"] == "red")
        
        if not red_alive:
            match["finished"] = True
            match["winner"] = "blue"
            await broadcast_in_match(mid, {"type": "match_end", "winner": "blue"})
            for n in match["blue"]:
                if n in players and not players[n].get("is_bot"):
                    players[n]["wins"] += 1
            for n in match["red"]:
                if n in players and not players[n].get("is_bot"):
                    players[n]["losses"] += 1
            save_data()
            break
        if not blue_alive:
            match["finished"] = True
            match["winner"] = "red"
            await broadcast_in_match(mid, {"type": "match_end", "winner": "red"})
            for n in match["red"]:
                if n in players and not players[n].get("is_bot"):
                    players[n]["wins"] += 1
            for n in match["blue"]:
                if n in players and not players[n].get("is_bot"):
                    players[n]["losses"] += 1
            save_data()
            break


def find_player_unit(match, nick):
    for u in match["units"]:
        if u["nick"] == nick:
            return u
    return None


def enemies_on_line(match, line, my_team):
    enemy_team = "red" if my_team == "blue" else "blue"
    return [u for u in match["units"] if u["alive"] and u["line"] == line and u["team"] == enemy_team]


async def start_match(blue, red):
    mid = str(random.randint(10000, 99999))
    matches[mid] = make_match_state(blue, red)
    for n in blue + red:
        player_match[n] = mid
    
    await broadcast_in_match(mid, {
        "type": "match_start",
        "match_id": mid,
        "blue": blue, "red": red,
    })
    asyncio.create_task(match_tick(mid))
    print(f"[СЕРВЕР] Матч {mid} начался: {blue} vs {red}")


def spawn_bots(count):
    bots = []
    for _ in range(count):
        name = f"Bot{random.randint(100, 999)}"
        while name in players:
            name = f"Bot{random.randint(100, 999)}"
        players[name] = new_player(name)
        players[name]["is_bot"] = True
        players[name]["hero"] = random.choice(list(HEROES.keys()))
        bots.append(name)
    return bots


async def queue_timeout(nick):
    """Если 8 сек никто не присоединился — добиваем ботами."""
    await asyncio.sleep(8)
    if nick not in queue:
        return
    
    current = queue[:]
    del queue[:]
    
    # добиваем до 6
    needed = 6 - len(current)
    if needed > 0:
        bots = spawn_bots(needed)
        current += bots
    
    random.shuffle(current)
    await start_match(current[:3], current[3:])


async def handle(ws, nick, data):
    p = players.get(nick)
    if not p:
        return
    
    cmd = data.get("cmd")
    match_id = player_match.get(nick)
    
    # ═══ ЧАТЫ ═══
    if cmd == "gc":
        text = str(data.get("text", ""))[:200]
        if text.strip():
            chat_gc.append((nick, text))
            if len(chat_gc) > 100:
                chat_gc.pop(0)
            await broadcast({"type": "gc", "from": nick, "text": text})
        return
    
    if cmd == "tc":
        if not match_id:
            await send(ws, {"type": "error", "text": "Ты не в игре"})
            return
        text = str(data.get("text", ""))[:200]
        if text.strip():
            match = matches.get(match_id)
            if not match:
                return
            my_team = "blue" if nick in match["blue"] else "red"
            for n in (match["blue"] if my_team == "blue" else match["red"]):
                await send_to_nick(n, {"type": "tc", "from": nick, "text": text})
        return
    
    if cmd == "pm":
        target = data.get("to")
        text = str(data.get("text", ""))[:200]
        if target in players:
            await send_to_nick_list(target, {"type": "pm", "from": nick, "text": text})
            await send(ws, {"type": "pm", "from": nick, "text": text})
        return
    
    # ═══ ДРУЗЬЯ ═══
    if cmd == "friend_add":
        target = data.get("nick")
        if target in players and target not in p["friends"]:
            p["friends"].append(target)
            save_data()
            await send(ws, {"type": "info", "text": f"{target} в друзьях"})
        return
    
    if cmd == "friend_del":
        target = data.get("nick")
        if target in p["friends"]:
            p["friends"].remove(target)
            save_data()
            await send(ws, {"type": "info", "text": f"{target} удалён"})
        return
    
    if cmd == "friends":
        result = [f"{'🟢' if f in online.values() else '⚫'} {f}" for f in p["friends"]]
        await send(ws, {"type": "info", "text": "Друзья:\n" + ("\n".join(result) if result else "Нет")})
        return
    
    # ═══ ВЫБОР ГЕРОЯ (вне матча) ═══
    if cmd == "hero":
        hero = data.get("hero")
        if hero in HEROES:
            p["hero"] = hero
            save_data()
            await send(ws, {"type": "info", "text": f"Герой: {HEROES[hero]['name']}"})
        return
    
    # ═══ БЫСТРАЯ ИГРА (С РАНДОМАМИ + БОТАМИ) ═══
    if cmd == "queue":
        if nick in player_match:
            await send(ws, {"type": "error", "text": "Ты в мат.clearче"})
            return
        if nick in queue:
            queue.remove(nick)
            await send(ws, {"type": "info", "text": "Вышел из очереди"})
            return
        
        queue.append(nick)
        await send(ws, {"type": "info", "text": f"В очереди: {len(queue)}/6"})
        
        if len(queue) >= 6:
            nicks = queue[:6]
            del queue[:6]
            random.shuffle(nicks)
            await start_match(nicks[:3], nicks[3:])
        else:
            asyncio.create_task(queue_timeout(nick))
        return
    
    # ═══ ЛОББИ ═══
    if cmd == "lobby_list":
        await send(ws, {"type": "lobby_list", "lobbies": lobby_list()})
        return
    
    if cmd == "lobby_create":
        # выйти из старого
        for lid, l in list(lobbies.items()):
            if nick in l["players"]:
                l["players"].remove(nick)
                l["picks"].pop(nick, None)
                if not l["players"]:
                    del lobbies[lid]
        
        lid = str(random.randint(1000, 9999))
        lobbies[lid] = {
            "host": nick,
            "players": [nick],
            "picks": {},
            "size": 3,
        }
        await send(ws, {"type": "info", "text": f"Лобби {lid} создано"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_join":
        lid = str(data.get("id"))
        if lid not in lobbies:
            await send(ws, {"type": "error", "text": "Нет лобби"})
            return
        l = lobbies[lid]
        if len(l["players"]) >= l["size"] * 2:
            await send(ws, {"type": "error", "text": "Полно"})
            return
        if nick not in l["players"]:
            l["players"].append(nick)
        await send(ws, {"type": "info", "text": f"Ты в лобби {lid}"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_leave":
        for lid, l in list(lobbies.items()):
            if nick in l["players"]:
                l["players"].remove(nick)
                l["picks"].pop(nick, None)
                if not l["players"]:
                    del lobbies[lid]
                elif l["host"] == nick:
                    l["host"] = l["players"][0]
                break
        await send(ws, {"type": "info", "text": "Вышел из лобби"})
        await lobby_broadcast()
        return
    
    if cmd == "lobby_pick":
        hero = data.get("hero")
        if hero not in HEROES:
            return
        for lid, l in lobbies.items():
            if nick in l["players"]:
                l["picks"][nick] = hero
                p["hero"] = hero
                await send(ws, {"type": "info", "text": f"Выбран {HEROES[hero]['name']}"})
                await lobby_broadcast()
                
                # все выбрали? старт
                if len(l["picks"]) == len(l["players"]) and len(l["players"]) >= 2:
                    # собираем команды
                    nicks = l["players"][:]
                    needed = 6 - len(nicks)
                    bots = spawn_bots(needed) if needed > 0 else []
                    all_nicks = nicks + bots
                    random.shuffle(all_nicks)
                    
                    del lobbies[lid]
                    await start_match(all_nicks[:3], all_nicks[3:])
                break
        return
    
    if cmd == "lobby_start":
        lid = None
        for _lid, l in lobbies.items():
            if nick in l["players"]:
                lid = _lid
                break
        if not lid:
            await send(ws, {"type": "error", "text": "Не в лобби"})
            return
        l = lobbies[lid]
        if l["host"] != nick:
            await send(ws, {"type": "error", "text": "Только хост"})
            return
        
        nicks = l["players"][:]
        needed = 6 - len(nicks)
        bots = spawn_bots(needed) if needed > 0 else []
        all_nicks = nicks + bots
        random.shuffle(all_nicks)
        
        del lobbies[lid]
        await start_match(all_nicks[:3], all_nicks[3:])
        await lobby_broadcast()
        return
    
    # ═══ ИГРОВЫЕ КОМАНДЫ ═══
    if not match_id:
        await send(ws, {"type": "error", "text": "Не в игре"})
        return
    
    match = matches.get(match_id)
    if not match or match["finished"]:
        await send(ws, {"type": "error", "text": "Матч окончен"})
        return
    
    unit = find_player_unit(match, nick)
    if not unit:
        return
    
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
            await send(ws, {"type": "log", "text": "Нет врагов"})
            return
        
        target = enemies_here[0]
        result = cast_skill(unit, target, skill_key)
        if result:
            for e in enemies_here:
                await send_to_nick(e["nick"], {"type": "log", "text": result})
            await send(ws, {"type": "log", "text": result})
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
        await send(ws, {"type": "heroes", "heroes": list(HEROES.keys())})
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
            if nick in queue:
                queue.remove(nick)
            for lid, l in list(lobbies.items()):
                if nick in l["players"]:
                    l["players"].remove(nick)
                    l["picks"].pop(nick, None)
                    if not l["players"]:
                        del lobbies[lid]
            await lobby_broadcast()


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
