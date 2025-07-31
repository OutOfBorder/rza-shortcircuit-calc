#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import math
import requests
from itertools import combinations
from copy import deepcopy
from dotenv import load_dotenv
import argparse

# ----------------- УТИЛИТЫ -----------------

def to_polar(re: float, im: float):
    """Комплекс → (модуль, угол в °)."""
    mag = math.hypot(re, im)
    ang = math.degrees(math.atan2(im, re))
    return mag, ang

def load_model(path="model4.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def find_breakers(model):
    """Возвращает [(id, name), ...] для Type=='breaker'."""
    out = []
    for el_id, el in model.get("elements", {}).items():
        if el.get("Type") == "breaker":
            out.append((el_id, el.get("Name", el_id)))
    return out

def extract_currents(resp_json):
    """
    Разбирает ответ tkzf/calc:
      { "<id>": { "I": [ [Re,Im], ... ] }, ... }
    Возвращает { id: (best_mag, best_ang) or None }.
    """
    res = {}
    for eid, dat in resp_json.items():
        arr = dat.get("I")
        if not isinstance(arr, list):
            res[eid] = None
            continue
        best = (0.0, 0.0)
        for c in arr:
            if isinstance(c, (list, tuple)) and len(c) == 2:
                mag, ang = to_polar(c[0], c[1])
                if mag > best[0]:
                    best = (mag, ang)
        res[eid] = best if best[0] > 1e-6 else None
    return res

# ----------------- ОСНОВНОЙ КОД -----------------

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Перебор отключений выключателей и поиск максимального тока КЗ")
    parser.add_argument("--k", type=int, default=1, help="число одновременно отключаемых выключателей")
    args = parser.parse_args()

    USER = os.getenv("LABRZA_USER")
    PASS = os.getenv("LABRZA_PASS")
    if not USER or not PASS:
        print("❌ Укажите LABRZA_USER и LABRZA_PASS в .env")
        return

    # --- Авторизация ---
    session = requests.Session()
    auth_url = "https://labrza.ru/api/v1/auth/login"
    r = session.post(
        auth_url,
        data={"grant_type": "password", "username": USER, "password": PASS},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
    print("✅ Авторизация прошла успешно.")

    # --- Загрузка модели и список выключателей ---
    model = load_model("model4.json")
    breakers = find_breakers(model)
    id2name = {bid: name for bid, name in breakers}

    print(f"\n🔌 Найдено выключателей: {len(breakers)}")
    for bid, name in breakers:
        print(f"  • {name} (id={bid})")

    tkz_url = "https://labrza.ru/api/v1/general/tkzf/calc"

    def do_tkzf(mdl):
        files = {"upload_file": ("model.json", json.dumps(mdl), "application/json")}
        resp = session.post(tkz_url, files=files)
        resp.raise_for_status()
        out = resp.json()
        if isinstance(out, str):
            out = json.loads(out)
        return out

    # --- 1) «Нормальный режим» через tkzf/calc (КЗ отключено) ---
    m_normal = deepcopy(model)
    for el in m_normal["elements"].values():
        if el.get("Type") == "short_circuit":
            el["faults"]["states"][0]["enabled"] = False

    print(f"\n⚙️ Расчёт «нормального режима» (КЗ отключено)…")
    try:
        resp_norm = do_tkzf(m_normal)
        norm_map = extract_currents(resp_norm)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        norm_map = {}

    print("\n📊 **Нормальный режим** — токи через выключатели:")
    for bid, name in breakers:
        v = norm_map.get(bid)
        if v:
            print(f"  • {name}: |I|={v[0]:.3f} kA ∠{v[1]:.1f}°")
        else:
            print(f"  • {name}: нет тока или ≈0")

    # --- 2) «Режим КЗ» без отключений ---
    print(f"\n⚙️ Расчёт режима КЗ (все выключатели включены)…")
    try:
        resp_fault0 = do_tkzf(model)
        fault0_map = extract_currents(resp_fault0)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        fault0_map = {}

    print("\n📊 **Режим КЗ** — токи через выключатели:")
    for bid, name in breakers:
        v = fault0_map.get(bid)
        if v:
            print(f"  • {name}: |I|={v[0]:.3f} kA ∠{v[1]:.1f}°")
        else:
            print(f"  • {name}: нет тока или ≈0")

    # --- 3) Перебор отключений k ---
    k = args.k
    all_ids = [bid for bid, _ in breakers]
    combos = list(combinations(all_ids, k))
    print(f"\n🔍 Перебор отключений по {k} (всего {len(combos)})\n")

    global_max = 0.0
    best_breaker_names = set()
    best_cases = []

    for idx, combo in enumerate(combos, 1):
        human = " и ".join(id2name[bid] for bid in combo)
        print(f"⚙️ [{idx}/{len(combos)}] Отключаем: {human}")

        m2 = deepcopy(model)
        for el_id in combo:
            el = m2["elements"].get(el_id)
            if el and el.get("Type") == "breaker":
                st = el["states"][0]
                st["AisClosed"] = st["BisClosed"] = st["CisClosed"] = False

        try:
            resp_f = do_tkzf(m2)
            f_map = extract_currents(resp_f)
            print("  ✅ Fault calc OK")
        except Exception as e:
            print(f"  ❌ Ошибка расчёта: {e}")
            f_map = {}

        local_max = 0.0
        local_max_breaker = None
        for bid, name in breakers:
            v = f_map.get(bid)
            if v:
                print(f"    • {name}: |I|={v[0]:.3f} kA ∠{v[1]:.1f}°")
                if v[0] > local_max:
                    local_max = v[0]
                    local_max_breaker = name
            else:
                print(f"    • {name}: нет тока")

        if local_max_breaker:
            print(f"    🔌 Max fault через {local_max_breaker} = {local_max:.3f} kA")

        # обновляем глобальный максимум
        if local_max > global_max + 1e-6:
            global_max = local_max
            best_breaker_names = {local_max_breaker}
            best_cases = [combo]
        elif abs(local_max - global_max) < 1e-6 and local_max_breaker:
            best_breaker_names.add(local_max_breaker)
            best_cases.append(combo)

        print()

    # --- Итоговый вывод ---
    if global_max > 1e-6:
        br_names = ", ".join(sorted(best_breaker_names))
        case_strs = []
        for comb in best_cases:
            human = " и ".join(id2name[bid] for bid in comb)
            case_strs.append(human)
        cases_joined = "; ".join(case_strs)
        print(f"✅ Результат: максимальный ток через выключатель {br_names} = "
              f"{global_max:.3f} kA при отключении {cases_joined}")
    else:
        print("✅ Результат: токи не обнаружены.")

    # сохраняем
    with open("tkz_nk_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "normal": norm_map,
            "fault0": fault0_map,
            "best_cases": best_cases,
            "global_max": global_max,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
