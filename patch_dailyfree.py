#!/usr/bin/env python3
"""Make DailyCarry its own seat: no index gate, no $0.25 cut, ATR stop stays."""
import os
import shutil
import py_compile

TARGET = "main.py"
BACKUP = "main.py.bak_dailyfree"

PAIRS = [
(
'''    DAILY_CARRY_MAX_MOVE = 0.45
    DAILY_CARRY_SPIKE_FRAC = 0.55
    DAILY_CARRY_FUNDING_LONG_MAX = 0.00030
    DAILY_CARRY_FUNDING_SHORT_MIN = -0.00010
''',
'''    DAILY_CARRY_MAX_MOVE = 0.80
    DAILY_CARRY_SPIKE_FRAC = 0.80
    DAILY_CARRY_FUNDING_LONG_MAX = 0.00080
    DAILY_CARRY_FUNDING_SHORT_MIN = -0.00050
'''
),
(
'''    if abs(ret7) < lo or abs(ret7) > hi:
        return None
    if abs(last) > abs(ret7) * float(getattr(config, "DAILY_CARRY_SPIKE_FRAC", 0.55)):
        return None
''',
'''    if abs(ret7) < lo or abs(ret7) > hi:
        return {"reject": "range"}
    if abs(last) > abs(ret7) * float(getattr(config, "DAILY_CARRY_SPIKE_FRAC", 0.80)):
        return {"reject": "spike"}
'''
),
(
'''    scored = await daily_score(symbol)
    side = str(trade.get("side") or "")
    rate = float(funds.get(symbol) or 0.0)
    drop = scored is None or not daily_funding_ok(side, rate)
    if scored and side == "BUY" and scored["score"] <= 0:
        drop = True
    if scored and side == "SELL" and scored["score"] >= 0:
        drop = True
''',
'''    scored = await daily_score(symbol)
    side = str(trade.get("side") or "")
    rate = float(funds.get(symbol) or 0.0)
    ok_score = bool(scored) and scored.get("score") is not None
    drop = (not ok_score) or (not daily_funding_ok(side, rate))
    if ok_score and side == "BUY" and scored["score"] <= 0:
        drop = True
    if ok_score and side == "SELL" and scored["score"] >= 0:
        drop = True
'''
),
(
'''    best = None
    for _, sym in liquid:
        if any(sym in trades for trades in active_trades.values()):
            continue
        scored = await daily_score(sym)
        if not scored:
            continue
        side = "BUY" if scored["score"] > 0 else "SELL"
        rate = float(funds.get(sym) or 0.0)
        if not daily_funding_ok(side, rate):
            continue
        if best is None or abs(scored["score"]) > abs(best["score"]):
            best = {"symbol": sym, "side": side, "funding": rate, **scored}
    if not best:
        logger.info(f"📅 DailyCarry | no trade | scanned={len(liquid)}")
        return
    sym = best["symbol"]
    side = best["side"]
    px = float(best["px"])
    if px <= 0:
        return
    idx_now = await get_index_direction()
    ok_idx, why_idx = index_entry_allowed(idx_now, side)
    if not ok_idx:
        logger.info(f"🚫 DAILY index {sym} | {why_idx}")
        return
''',
'''    best = None
    rejected = {"range": 0, "spike": 0, "funding": 0, "busy": 0, "none": 0}
    for _, sym in liquid:
        if any(sym in trades for trades in active_trades.values()):
            rejected["busy"] += 1
            continue
        scored = await daily_score(sym)
        if not scored or scored.get("score") is None:
            rejected[(scored or {}).get("reject") or "none"] += 1
            continue
        side = "BUY" if scored["score"] > 0 else "SELL"
        rate = float(funds.get(sym) or 0.0)
        if not daily_funding_ok(side, rate):
            rejected["funding"] += 1
            continue
        if best is None or abs(scored["score"]) > abs(best["score"]):
            best = {"symbol": sym, "side": side, "funding": rate, **scored}
    if not best:
        logger.info(
            f"📅 DailyCarry | no trade | scanned={len(liquid)} "
            f"range={rejected['range']} spike={rejected['spike']} "
            f"funding={rejected['funding']} busy={rejected['busy']}"
        )
        return
    sym = best["symbol"]
    side = best["side"]
    px = float(best["px"])
    if px <= 0:
        return
'''
),
(
'''            if getattr(config, "ENABLE_SAME_DIRECTION_CAP", True):
                same_n = count_open_side(side)
''',
'''            if getattr(config, "ENABLE_SAME_DIRECTION_CAP", True) and not (quality_report or {}).get("daily_carry"):
                same_n = count_open_side(side)
'''
),
(
'''            await place_tp_ladder(symbol, side, entry_price, stop_dist, qty, strength)
''',
'''            if not (quality_report or {}).get("daily_carry"):
                await place_tp_ladder(symbol, side, entry_price, stop_dist, qty, strength)
'''
),
(
'''            if qty > 0 and cut_usd > 0:
                dollar_dist = cut_usd / float(qty)
''',
'''            daily_lane = bool((quality_report or {}).get("daily_carry"))
            if qty > 0 and cut_usd > 0 and not daily_lane:
                dollar_dist = cut_usd / float(qty)
'''
),
(
'''            logger.info(f"📏 Exchange SL {symbol} | ${cut_usd:.2f} cap | dist={sl_dist:.8g} wide={wide_dist:.8g}")
''',
'''            if daily_lane:
                logger.info(f"📏 DailyCarry SL {symbol} | ATR dist={sl_dist:.8g}")
            else:
                logger.info(f"📏 Exchange SL {symbol} | ${cut_usd:.2f} cap | dist={sl_dist:.8g} wide={wide_dist:.8g}")
'''
),
(
'''                trade["peak_r"] = max(float(trade.get("peak_r") or current_r), current_r)
                await arm_one_r_lock(symbol, trade, entry_price, stop_dist, side)
                if float(trade.get("peak_r") or 0) < float(getattr(config, "R1_LOCK_PEAK_R", 1.00)):
                    await arm_dollar_breakeven(symbol, trade, current_price, entry_price, side)
''',
'''                trade["peak_r"] = max(float(trade.get("peak_r") or current_r), current_r)
                if not trade.get("daily_carry"):
                    await arm_one_r_lock(symbol, trade, entry_price, stop_dist, side)
                    if float(trade.get("peak_r") or 0) < float(getattr(config, "R1_LOCK_PEAK_R", 1.00)):
                        await arm_dollar_breakeven(symbol, trade, current_price, entry_price, side)
'''
),
(
'''                        await lock_open_profit(symbol, trade, peak_now, current_r, entry_price, stop_dist, side)
                        await arm_one_r_lock(symbol, trade, entry_price, stop_dist, side)
''',
'''                        if not trade.get("daily_carry"):
                            await lock_open_profit(symbol, trade, peak_now, current_r, entry_price, stop_dist, side)
                            await arm_one_r_lock(symbol, trade, entry_price, stop_dist, side)
'''
),
(
'''                        try:
                            await raise_profit_stop(symbol, trade, peak_now)
                        except Exception:
                            pass
''',
'''                        try:
                            if not trade.get("daily_carry"):
                                await raise_profit_stop(symbol, trade, peak_now)
                        except Exception:
                            pass
'''
),
(
'''                            elif open_usd <= -cut_usd:
''',
'''                            elif open_usd <= -cut_usd and not trade.get("daily_carry"):
'''
),
]


def fail(msg):
    shutil.copy2(BACKUP, TARGET)
    print(msg)
    print(f"restored from {BACKUP} — bot file was not changed")


def main():
    if not os.path.exists(TARGET):
        print(f"STOPPED missing {TARGET}")
        return
    shutil.copy2(TARGET, BACKUP)
    text = open(TARGET, encoding="utf-8").read()
    if "DailyCarry | no trade | scanned=" in text and "range={rejected" in text:
        fail("STOPPED this daily fix is already in this file")
        return
    for i, (old, new) in enumerate(PAIRS, 1):
        n = text.count(old)
        if n != 1:
            fail(f"STOPPED piece {i} count={n}")
            return
        text = text.replace(old, new, 1)
    open(TARGET, "w", encoding="utf-8").write(text)
    try:
        py_compile.compile(TARGET, doraise=True)
    except Exception as e:
        fail(f"STOPPED compile: {e}")
        return
    print(f"DONE pieces={len(PAIRS)}")
    print(f"backup={BACKUP}")


if __name__ == "__main__":
    main()
