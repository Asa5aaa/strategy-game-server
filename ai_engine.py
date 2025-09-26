
# ai_engine.py - adaptive utility-based AI engine (updated)
import random, math, copy

CARD_PRIORITY = {
    "petro": 0.9,
    "radar": 0.8,
    "defense": 0.7,
    "launcher": 0.85,
    "airport": 0.6
}

PRICES = {"launcher":1200, "radar":2000, "petro":2500, "defense":1500, "airport":1200}

def aggression_from_history(state):
    # Increase aggression if player has many offensive recent actions or AI has lost recently
    recent = state.get("recent_player_actions", [])
    offense = sum(1 for a in recent if 'launch' in a or 'attack' in a or 'drone' in a)
    defense = sum(1 for a in recent if 'defend' in a or 'radar' in a)
    base = 0.5
    base += 0.1 * (offense - defense)  # respond to player's offense
    # use player's win record to modulate (if player has many wins, AI more cautious)
    player_wins = state.get("player_offline_wins", 0) + state.get("player_online_wins", 0)
    if player_wins > 8:
        base -= 0.1
    return max(0.1, min(0.95, base))

def utility_score_build(card_type, state):
    money = state.get("money",0)
    # dynamic priority adjustments
    aggr = state.get("aggression", 0.5)
    if card_type == "petro":
        return CARD_PRIORITY["petro"] + (0.001 * max(0, 5000 - money))
    if card_type == "radar":
        if len(state.get("buildings_enemy",[]))>0 and not state.get("radar_active", False):
            return CARD_PRIORITY["radar"] + 0.1
    # if aggression high, favor launcher
    if card_type == "launcher":
        return CARD_PRIORITY["launcher"] + (aggr - 0.5) * 0.4
    return CARD_PRIORITY.get(card_type, 0.5)

def choose_build_action(state):
    affordable = []
    for t,p in PRICES.items():
        if state.get("money",0) >= p:
            affordable.append((t, utility_score_build(t,state)))
    if not affordable:
        return {"action":"wait", "reason":"not_enough_money"}
    total = sum(u for _,u in affordable)
    pick = random.random()*total
    upto = 0
    for t,u in affordable:
        upto += u
        if pick <= upto:
            return {"action":"build", "type":t, "price": PRICES[t]}
    return {"action":"build", "type": affordable[0][0], "price": PRICES[affordable[0][0]]}

def choose_attack_action(state):
    launchers = [b for b in state.get("buildings_enemy",[]) if b.get("type")=="launcher"]
    targets = state.get("buildings_you",[])
    if not targets or not launchers:
        return {"action":"wait"}
    def value(t):
        base = 1.0
        if t.get("type")=="petro": base = 2.0
        return base / max(1,t.get("hp",1))
    targets_sorted = sorted(targets, key=lambda t: -value(t))
    target = targets_sorted[0]
    launcher = launchers[0]
    p_hit = 1.0
    if any(x.get("type")=="defense" for x in state.get("buildings_you",[])):
        p_hit -= 0.1
    # adapt miss chance slightly by aggression
    aggr = state.get("aggression", 0.5)
    miss_chance = 0.08 - (aggr - 0.5) * 0.04
    if random.random() < max(0, miss_chance):
        return {"action":"attack", "from": launcher["id"], "target": target["id"], "expected_hit": False}
    return {"action":"attack", "from": launcher["id"], "target": target["id"], "expected_hit": True}

def decide_action(state):
    # compute aggression from history
    aggr = aggression_from_history(state)
    state['aggression'] = aggr
    # Defensive priority if losing badly
    if state.get("hp_enemy",100) - state.get("hp_you",100) < -20:
        if state.get("money",0) > 1400:
            return {"action":"build","type":"defense"}
    if state.get("money",0) > 2000 and state.get("radar_needed", False):
        return {"action":"use_radar"}
    # if launcher available and aggression high, attack more
    if any(b["type"]=="launcher" for b in state.get("buildings_enemy",[])) and state.get("buildings_you"):
        if random.random() < aggr:
            return choose_attack_action(state)
    # otherwise try to build based on utility
    return choose_build_action(state)
