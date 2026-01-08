import dateparser, pytz, re
from datetime import timedelta, datetime, time
from typing import Dict, List, Optional, Tuple
import numpy as np
from .appliance import Appliance



def create_time_intervals(T:int, delta:int) -> List:
    #now = datetime.now()
    now = _now_local("Europe/Rome")
    step = timedelta(minutes=delta)
    time_intervals = []

    for i in range(T):
        time_intervals.append(now)
        now+=step
        
    return time_intervals


def find_min_sum(grid_import, time_intervals, time_window: int=0) -> Tuple[datetime, datetime, float]:

    min_sum=float('inf')
    start = end = 0

    for i in range(0, len(grid_import) - time_window + 1):
        current_sum = np.sum(grid_import[i:i+time_window])  
        #print(i, "import:", grid_import[i], "somma temp. da ", i, "a", i + time_window - 1, current_sum)
        if current_sum < min_sum:
            min_sum = current_sum
            start = i

    end = start+time_window
    start_time = time_intervals[start]
    end_time= time_intervals[end]

    return start_time, end_time, round(min_sum, 2)


def get_idx(pred_intervals:List[datetime], appl_time: datetime) -> int:
    """
    restituisce la posizione dell'array in cui l'orario di avvio dell'elettrodomestico rientra nella fascia oraria 
    di predizione 
    """
    start_idx=0
    for i, interval in enumerate(pred_intervals):
        #print(pv_interval, i)
        if appl_time == interval:
            start_idx = i
        elif appl_time > interval and appl_time <= pred_intervals[i+1]:
            start_idx = i+1

    return start_idx

# ============================================================
# -- prendi orario e applicalo a consumi appliance
# ============================================================

def map_consumption(app_str, user_preference, predicted_load=[]):
    app = Appliance(app_str)
    now = _now_local("Europe/Rome")
    time_steps = 24*60
    time_intervals = create_time_intervals(time_steps,1) # T=il numero di step, delta=risoluzione (1 min)
    print(time_intervals[0])
    parsed_pref = parse_time_constraint(user_preference)
    print(parsed_pref)
    app.start_time = parsed_pref['start'] if parsed_pref['start'] is not None else now #passo all'eltettrodom. l'avvio identificato nella custom action (o user-defined o datetime.now())
    app.end_time = parsed_pref['end'] if parsed_pref['end'] is not None else app.start_time + timedelta(hours=2)
    appliance_consumption = [app.avg_demand*1000 if t >= app.start_time and t < app.end_time else 0 for t in time_intervals]
 
    if predicted_load == []:
        predicted_load = [0.1]*(time_steps) 

    tot_load = list(map(lambda x,y: x+y, appliance_consumption, predicted_load)) #
    print(app.start_idx, app.start_time, app.cycle_duration, tot_load)

    return tot_load


# ============================================================
# Helpers
# ============================================================

def _now_local(timezone: str) -> datetime:
    """Current local time without tzinfo."""
    return datetime.now(pytz.timezone(timezone)).replace(tzinfo=None)


# ============================================================
# Relative time parser
# ============================================================

def parse_relative_delta(text: str) -> Optional[timedelta]:
    """
    Interpreta espressioni relative come:
    - un'ora, due ore, quattro ore circa
    - 1h e mezza
    - qualche ora
    - 30 minuti, mezz’ora, un quarto d’ora
    """
    
    text = text.lower().strip()
    text = text.replace("circa", "").strip()

    # --- casi particolari ---
    if "qualche" in text:  
        return timedelta(hours=2)

    if "mezz" in text:  
        return timedelta(minutes=30)

    if "quarto" in text:  
        return timedelta(minutes=15)

    # "1h e mezza"
    m = re.match(r"(\d+)\s*h\s*e\s*mezz", text)
    if m:
        h = int(m.group(1))
        return timedelta(hours=h, minutes=30)

    # numeri tipo: "x ore", "x ora", "x h"
    m = re.match(r"(\d+)\s*(ora|ore|h)\b", text)
    if m:
        return timedelta(hours=int(m.group(1)))

    # numeri tipo: "x minuti"
    m = re.match(r"(\d+)\s*(minuti|minuto|min)", text)
    if m:
        return timedelta(minutes=int(m.group(1)))

    # numeri scritti in lettere
    words_to_hours = {
        "un": 1, "una": 1, "uno": 1, "un'": 1,
        "due": 2, "tre": 3, "quattro": 4,
        "cinque": 5, "sei": 6
    }
    for word, h in words_to_hours.items():
        if text.startswith(word):
            return timedelta(hours=h)

    return None


# ============================================================
# Main Parser
# ============================================================

def parse_time_constraint(expr: str, timezone="Europe/Rome") -> Dict:
    """
    Ritorna un dict standardizzato:

    {
        "type": "point" | "range" | None,
        "start": datetime | None,
        "end": datetime | None
    }
    """
    if not expr:
        return {"type": None, "start": None, "end": None}

    expr_low = expr.lower().strip()
    now = _now_local(timezone)

    # ============================================================
    # 1) Espressioni relative
    # ============================================================

    # ENTRO X TEMPO → range da ora a ora+X
    m = re.match(r"entro\s+(.*)", expr_low)
    if m:
        delta = parse_relative_delta(m.group(1))
        if delta:
            return {
                "type": "range",
                "start": now,
                "end": now + delta
            }

    # TRA X TEMPO → punto singolo nel futuro
    m = re.match(r"(tra|fra)\s+(.*)", expr_low)
    if m:
        delta = parse_relative_delta(m.group(2))
        if delta:
            return {
                "type": "point",
                "start": now + delta,
                "end": None
            }

    # DOPO LE X
    m = re.match(r"dopo\s+le\s+(.*)", expr_low)
    if m:
        parsed = dateparser.parse(
            m.group(1),
            languages=["it"],
            settings={"PREFER_DATES_FROM": "future"}
        )
        if parsed:
            dt = parsed.astimezone(pytz.timezone(timezone)).replace(tzinfo=None)
            return {"type": "range", "start": dt, "end": None}

    # DALLE X
    m = re.match(r"(dalle|da)\s+(.*)", expr_low)
    if m:
        raw_time = m.group(2).strip()
        
        # --- Caso 1: è solo un numero → interpretalo come ORA ---
        if re.match(r"^\d{1,2}$", raw_time):
            hour = int(raw_time)
            now = datetime.now(pytz.timezone(timezone))
            dt = now.replace(hour=hour, minute=0, second=0, microsecond=0).replace(tzinfo=None)
            return {"type": "range", "start": dt, "end": None}
        
        # --- Caso 2: parole riconoscibili ("mezzogiorno", "mezzanotte") ---
        alias = {
            "mezzogiorno": 12,
            "mezzanotte": 0
        }
        if raw_time in alias:
            hour = alias[raw_time]
            now = datetime.now(pytz.timezone(timezone))
            dt = now.replace(hour=hour, minute=0, second=0, microsecond=0).replace(tzinfo=None)
            return {"type": "range", "start": dt, "end": None}
    
        # --- Caso 3: fallback → usa dateparser ---
        parsed = dateparser.parse(
            raw_time,
            languages=["it"],
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": timezone,
                "RETURN_AS_TIMEZONE_AWARE": True
            }
        )
    
        if parsed:
            dt = parsed.astimezone(pytz.timezone(timezone)).replace(tzinfo=None)
            return {"type": "range", "start": dt, "end": None}


    # ============================================================
    # 2) Intervalli "dalle X alle Y"
    # ============================================================

    m = re.match(
        r"(dalle|dal|da)\s+(.*?)\s+(alle|fino alle|fino a|fino)\s+(.*)",
        expr_low
    )
    
    if m:
        start_expr, end_expr = m.group(2).strip(), m.group(4).strip()
        now = datetime.now(pytz.timezone(timezone))
    
        def parse_time_part(part):
            """Parsa una delle due estremità dell'intervallo."""
    
            # Caso 1: solo numero → interpretalo come ORA
            if re.match(r"^\d{1,2}$", part):
                hour = int(part)
                return now.replace(hour=hour, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    
            # Caso 2: alias noti
            alias = {
                "mezzogiorno": 12,
                "mezzanotte": 0
            }
            if part in alias:
                hour = alias[part]
                return now.replace(hour=hour, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    
            # Caso 3: fallback → usa dateparser
            parsed = dateparser.parse(
                part,
                languages=["it"],
                settings={
                    "PREFER_DATES_FROM": "future",
                    "TIMEZONE": timezone,
                    "RETURN_AS_TIMEZONE_AWARE": True
                }
            )
            if parsed:
                return parsed.astimezone(pytz.timezone(timezone)).replace(tzinfo=None)
    
            return None
    
        start_dt = parse_time_part(start_expr)
        end_dt = parse_time_part(end_expr)
    
        if start_dt and end_dt:
            return {
                "type": "range",
                "start": start_dt,
                "end": end_dt
            }

    # ============================================================
    # 3) Orari semplici: "le 19", "alle 14", "verso le 8"
    # ============================================================

    # "le 14"
    m = re.match(r"(le|alle|verso le)\s+(\d{1,2})$", expr_low)
    if m:
        hour = int(m.group(2))
        start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if start < now:
            start += timedelta(days=1)
        return {"type": "point", "start": start, "end": None}

    # ============================================================
    # 4) Fallback: dateparser generale
    # ============================================================

    dt = dateparser.parse(
        expr_low,
        languages=['it'],
        settings={
            'TIMEZONE': timezone,
            'RETURN_AS_TIMEZONE_AWARE': True,
            'PREFER_DATES_FROM': 'future'
        }
    )
    if dt:
        dt = dt.astimezone(pytz.timezone(timezone)).replace(tzinfo=None)
        return {"type": "point", "start": dt, "end": None}

    # ============================================================
    # Nessuna interpretazione possibile
    # ============================================================

    return {"type": None, "start": None, "end": None}



# ============================================================
# ESTRAZIONE ENTITA' DA ENUNCIATO
# ============================================================

def extract_entity_text(text, entity_name):
    for ent in tracker.latest_message.get("entities", []):
        if ent.get("entity") == entity_name:
            return text[ent["start"]:ent["end"]]
    return None


# ============================================================
# ============================================================
if __name__ == "__main__":
    tests = [
        "entro un'ora",
        "tra quattro ore circa",
        "tra qualche ora",
        "dalle 10 di mattina fino alle 15",
        "dopo le 18",
        "alle 21",
        "le 8",
        "domani alle 7",
        "mercoledì alle 14",
        "alle 9,30",
        "dalle 10:30",
        "alle 8 e mezza",
        "per le 8 e mezzo"
    ]

    for t in tests:
        print(t, "→", parse_time_constraint(t))

    user_pref = "alle 2"
    user_pref = "dalle 14 alle 15"
    #constr = parse_time_constraint(user_pref)
    #print(constr)
    map_consumption("hvac", user_pref)

