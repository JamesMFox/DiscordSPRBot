from typing import Optional

SPR_CLASS_CHART = [
    {"class": "A", "tier": "A1", "min": 0, "max": 99},
    {"class": "A", "tier": "A2", "min": 100, "max": 199},
    {"class": "A", "tier": "A-ELITE", "min": 200, "max": 299},

    {"class": "B", "tier": "B1", "min": 300, "max": 399},
    {"class": "B", "tier": "B2", "min": 400, "max": 499},
    {"class": "B", "tier": "B3", "min": 500, "max": 599},
    {"class": "B", "tier": "B-ELITE", "min": 600, "max": 699},

    {"class": "C", "tier": "C1", "min": 700, "max": 799},
    {"class": "C", "tier": "C2", "min": 800, "max": 849},
    {"class": "C", "tier": "C-ELITE", "min": 850, "max": 899},

    {"class": "D", "tier": "D1", "min": 900, "max": 999},
    {"class": "D", "tier": "D2", "min": 1000, "max": 1049},
    {"class": "D", "tier": "D3", "min": 1050, "max": 1099},
    {"class": "D", "tier": "D4", "min": 1100, "max": 1199},
    {"class": "D", "tier": "D-ELITE", "min": 1200, "max": 1399},

    {"class": "E", "tier": "E1", "min": 1400, "max": 1499},
    {"class": "E", "tier": "E2", "min": 1500, "max": 1599},
    {"class": "E", "tier": "E3", "min": 1600, "max": 1699},
    {"class": "E", "tier": "E-ELITE", "min": 1700, "max": 1799},

    {"class": "F", "tier": "F1", "min": 1800, "max": 1899},
    {"class": "F", "tier": "F2", "min": 1900, "max": 1999},
    {"class": "F", "tier": "F3", "min": 2000, "max": 2099},
    {"class": "F", "tier": "F-ELITE", "min": 2100, "max": 2199},

    {"class": "G", "tier": "G1", "min": 2200, "max": 2299},
    {"class": "G", "tier": "G2", "min": 2300, "max": 2399},
    {"class": "G", "tier": "G3", "min": 2400, "max": 2499},
    {"class": "G", "tier": "G-ELITE", "min": 2500, "max": 2599},

    {"class": "H", "tier": "H1", "min": 2600, "max": 2799},
    {"class": "H", "tier": "H2", "min": 2800, "max": 2999},
    {"class": "H", "tier": "H3", "min": 3000, "max": 3199},
    {"class": "H", "tier": "H-ELITE", "min": 3200, "max": 3399},

    {"class": "I", "tier": "I1", "min": 3400, "max": 3599},
    {"class": "I", "tier": "I2", "min": 3600, "max": 3799},
    {"class": "I", "tier": "I3", "min": 3800, "max": 3999},
    {"class": "I", "tier": "I-ELITE", "min": 4000, "max": 4199},

    {"class": "J", "tier": "J1", "min": 4200, "max": 4399},
    {"class": "J", "tier": "J2", "min": 4400, "max": 4599},
    {"class": "J", "tier": "J3", "min": 4600, "max": 4799},
    {"class": "J", "tier": "J-ELITE", "min": 4800, "max": 4999},

    {"class": "ELITE", "tier": "ELITE", "min": 5000, "max": None},
]

CLASS_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "ELITE"]

ROLE_TO_RANK_DATA = {
    "gold i": {"rank_role": "Gold I", "spr": 1050},
    "gold ii": {"rank_role": "Gold II", "spr": 1100},
    "gold iii": {"rank_role": "Gold III", "spr": 1300},
    "platinum i": {"rank_role": "Platinum I", "spr": 1400},
    "platinum ii": {"rank_role": "Platinum II", "spr": 1500},
    "platinum iii": {"rank_role": "Platinum III", "spr": 1750},
    "diamond i": {"rank_role": "Diamond I", "spr": 1800},
    "diamond ii": {"rank_role": "Diamond II", "spr": 2000},
    "diamond iii": {"rank_role": "Diamond III", "spr": 2450},
    "champ i": {"rank_role": "Champ I", "spr": 2500},
    "champ ii": {"rank_role": "Champ II", "spr": 2800},
    "champ iii": {"rank_role": "Champ III", "spr": 3350},
    "grand champ i": {"rank_role": "Grand Champ I", "spr": 3400},
    "grand champ ii": {"rank_role": "Grand Champ II", "spr": 3700},
    "grand champ iii": {"rank_role": "Grand Champ III", "spr": 4500},
    "supersonic legend": {"rank_role": "Supersonic Legend", "spr": 5000},
}


def normalize_role_name(role_name: str) -> str:
    return role_name.strip().lower()

def get_rank_data_from_discord_roles(member_roles):
    matches = []

    for role in member_roles:
        normalized_name = normalize_role_name(role.name)
        rank_data = ROLE_TO_RANK_DATA.get(normalized_name)

        if rank_data is not None:
            matches.append(rank_data)

    if not matches:
        return None

    return max(matches, key=lambda item: item["spr"])

def get_class_info_from_spr(spr: int) -> Optional[dict]:
    # ------------------------
    # Return the class/tier info for a given SPR.
    # Example return:
    # {
    #    "class": "F",
    #    "tier": "F2",
    #    "min": 1900,
    #    "max": 1999
    # }
    # ------------------------
    for entry in SPR_CLASS_CHART:
        min_spr = entry["min"]
        max_spr = entry["max"]

        if max_spr is None:
            if spr >= min_spr:
                return entry

        elif min_spr <= spr <= max_spr:
            return entry

    return None

def get_class_from_spr(spr: int) -> Optional[str]:
    # Return only the class name for a given SPR.
    info = get_class_info_from_spr(spr)
    return info["class"] if info else None

def get_class_max_spr(class_name: str) -> int | None:
    # Return the highest SPR allowed for a class.
    # ELITE has no cap, so return None.

    class_entries = [entry for entry in SPR_CLASS_CHART if entry["class"] == class_name]

    if not class_entries:
        return None

    max_values = [entry["max"] for entry in class_entries if entry["max"] is not None]

    if not max_values:
        return None

    return max(max_values)

def clamp_spr_to_class_cap(current_spr: int, new_spr: int) -> int:
    # Clamp a new SPR value so it cannot exceed the max SPR of the player's
    # current class before the change.
    # ELITE has no cap.

    current_class = get_class_from_spr(current_spr)

    if current_class is None:
        return new_spr

    class_max = get_class_max_spr(current_class)

    if class_max is None:
        return new_spr

    return min(new_spr, class_max)

def get_tier_from_spr(spr: int) -> Optional[str]:
    # Return only the tier name for a given SPR.
    info = get_class_info_from_spr(spr)
    return info["tier"] if info else None

def is_elite_tier(spr: int) -> bool:
    # Return True if the current SPR is in an Elite tier.
    info = get_class_info_from_spr(spr)

    if not info:
        return False

    return "ELITE" in info["tier"]

def get_next_class(current_class: str) -> Optional[str]:
    # Return the next class after the current one, or None if already top class.
    if current_class not in CLASS_ORDER:
        return None

    index = CLASS_ORDER.index(current_class)

    if index + 1 >= len(CLASS_ORDER):
        return None

    return CLASS_ORDER[index + 1]

def same_class(spr1: int, spr2: int) -> bool:
    # Return True if both SPR values are in the same class.
    return get_class_from_spr(spr1) == get_class_from_spr(spr2)

def get_lowest_tier_of_class(class_name: str) -> Optional[dict]:
    # Return the first/lowest tier entry for a given class.
    for entry in SPR_CLASS_CHART:
        if entry["class"] == class_name:
            return entry
    return None

def is_lowest_tier_of_class(rank_role: str, target_class: str) -> bool:
    if not rank_role:
        return False

    normalized_role = str(rank_role).strip().lower()
    normalized_class = str(target_class).strip().lower()

    # Example expected role format: "gold-1" or "gold 1"
    return normalized_role in {
        f"{normalized_class}-1",
        f"{normalized_class} 1",
    }