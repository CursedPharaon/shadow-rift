# shared.py — общие данные для сервера и клиента

HEROES = {
    "vermil": {
        "name": "Vermil", "role": "Mage",
        "hp": 1000, "mp": 500, "dmg": 80,
        "skills": {
            "1": {"name": "Атака", "dmg": 150, "mp": 30, "cd": 8},
            "2": {"name": "Стан",  "dmg": 50,  "mp": 50, "cd": 12, "stun": 2},
            "3": {"name": "Руд",   "dmg": 250, "mp": 80, "cd": 15},
        },
    },
    "aron": {
        "name": "Aron", "role": "Assassin",
        "hp": 600, "mp": 340, "dmg": 180,
        "skills": {
            "1": {"name": "Удар",  "dmg": 220, "mp": 40, "cd": 8},
            "2": {"name": "Стан",  "dmg": 80,  "mp": 60, "cd": 12, "stun": 2},
            "3": {"name": "Казнь", "dmg": 400, "mp": 100, "cd": 18},
        },
    },
    "koloss": {
        "name": "Koloss", "role": "Tank",
        "hp": 1400, "mp": 750, "dmg": 56,
        "skills": {
            "1": {"name": "Сокрушение", "dmg": 120, "mp": 40, "cd": 8},
            "2": {"name": "Стан",       "dmg": 40,  "mp": 60, "cd": 12, "stun": 3},
            "3": {"name": "Ярость",     "dmg": 300, "mp": 90, "cd": 20},
        },
    },
    "luna": {
        "name": "Luna", "role": "Mage",
        "hp": 850, "mp": 600, "dmg": 70,
        "skills": {
            "1": {"name": "Луч",       "dmg": 180, "mp": 40, "cd": 7},
            "2": {"name": "Оковы",     "dmg": 60,  "mp": 55, "cd": 12, "stun": 2},
            "3": {"name": "Метеор",    "dmg": 320, "mp": 100, "cd": 18},
        },
    },
    "shadow": {
        "name": "Shadow", "role": "Assassin",
        "hp": 700, "mp": 400, "dmg": 160,
        "skills": {
            "1": {"name": "Порез",     "dmg": 200, "mp": 35, "cd": 6},
            "2": {"name": "Дымка",     "dmg": 0,   "mp": 50, "cd": 14, "stun": 1},
            "3": {"name": "Тень",      "dmg": 380, "mp": 90, "cd": 16},
        },
    },
    "titan": {
        "name": "Titan", "role": "Tank",
        "hp": 1600, "mp": 500, "dmg": 60,
        "skills": {
            "1": {"name": "Щит",       "dmg": 100, "mp": 30, "cd": 9},
            "2": {"name": "Оглушение", "dmg": 50,  "mp": 55, "cd": 13, "stun": 3},
            "3": {"name": "Земля",     "dmg": 220, "mp": 80, "cd": 18},
        },
    },
    "ember": {
        "name": "Ember", "role": "Mage",
        "hp": 800, "mp": 650, "dmg": 75,
        "skills": {
            "1": {"name": "Огонь",   "dmg": 170, "mp": 35, "cd": 7},
            "2": {"name": "Пламя",   "dmg": 90,  "mp": 60, "cd": 12, "stun": 2},
            "3": {"name": "Инферно", "dmg": 340, "mp": 110, "cd": 20},
        },
    },
    "frost": {
        "name": "Frost", "role": "Support",
        "hp": 900, "mp": 700, "dmg": 55,
        "skills": {
            "1": {"name": "Лёд",      "dmg": 140, "mp": 40, "cd": 8},
            "2": {"name": "Заморозка","dmg": 60,  "mp": 60, "cd": 12, "stun": 3},
            "3": {"name": "Буря",     "dmg": 260, "mp": 95, "cd": 17},
        },
    },
    "raven": {
        "name": "Raven", "role": "Assassin",
        "hp": 650, "mp": 420, "dmg": 170,
        "skills": {
            "1": {"name": "Клюв",    "dmg": 230, "mp": 40, "cd": 7},
            "2": {"name": "Крик",    "dmg": 70,  "mp": 55, "cd": 12, "stun": 2},
            "3": {"name": "Пикирование","dmg": 420,"mp": 100, "cd": 18},
        },
    },
    "seraph": {
        "name": "Seraph", "role": "Support",
        "hp": 950, "mp": 800, "dmg": 50,
        "skills": {
            "1": {"name": "Свет",     "dmg": 130, "mp": 40, "cd": 8},
            "2": {"name": "Благословение", "dmg": 40, "mp": 70, "cd": 14, "stun": 2},
            "3": {"name": "Кара",     "dmg": 300, "mp": 110, "cd": 18},
        },
    },
    "viking": {
        "name": "Viking", "role": "Fighter",
        "hp": 1200, "mp": 400, "dmg": 100,
        "skills": {
            "1": {"name": "Топор",   "dmg": 190, "mp": 35, "cd": 8},
            "2": {"name": "Рывок",   "dmg": 90,  "mp": 50, "cd": 12, "stun": 2},
            "3": {"name": "Берсерк", "dmg": 350, "mp": 90, "cd": 18},
        },
    },
    "witch": {
        "name": "Witch", "role": "Mage",
        "hp": 750, "mp": 700, "dmg": 85,
        "skills": {
            "1": {"name": "Проклятие","dmg": 160, "mp": 45, "cd": 7},
            "2": {"name": "Куклы",    "dmg": 75,  "mp": 60, "cd": 12, "stun": 2},
            "3": {"name": "Смерть",   "dmg": 380, "mp": 120, "cd": 20},
        },
    },
}
