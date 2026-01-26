import asyncio
import websockets
import json
import os
import pandas as pd
from dotenv import load_dotenv
import requests
import time
from collections import deque
from datetime import datetime

load_dotenv()
SLACK_URL = os.getenv("SLACK_URL")

TARGETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]
price_queues = {code: deque(maxlen=50) for code in TARGETS}

# 💾 세이브 파일 이름
WALLET_FILE = "wallet.json"
BUY_AMOUNT = 1_000_000 

# 쿨타임
last_trade_time = {code: 0 for code in TARGETS}
TRADE_COOLDOWN = 60

# --- 💾 저장/불러오기 기능 추가 ---

def save_wallet(wallet_data):
    """지갑 상태를 JSON 파일로 저장"""
    try:
        with open(WALLET_FILE, 'w', encoding='utf-8') as f:
            json.dump(wallet_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"❌ 세이브 실패: {e}")

def load_wallet():
    """파일이 있으면 불러오고, 없으면 초기값 리턴"""
    if os.path.exists(WALLET_FILE):
        try:
            with open(WALLET_FILE, 'r', encoding='utf-8') as f:
                print("📂 기존 지갑(세이브 파일)을 불러옵니다.")
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 파일 읽기 실패(초기화): {e}")
            
    # 파일이 없으면 초기 상태 리턴
    print("✨ 새 지갑을 생성합니다.")
    return {
        "KRW": 10_000_000, 
        "COINS": {code: {"vol": 0.0, "avg": 0.0} for code in TARGETS}
    }

# 프로그램 시작 시 지갑 로드
WALLET = load_wallet()

# ----------------------------------

def send_slack(msg):
    if not SLACK_URL: return
    try:
        requests.post(SLACK_URL, json={"text": msg})
    except Exception as e:
        print(f"슬랙 전송 실패: {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period: return None
    series = pd.Series(prices)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def buy_coin(code, price):
    if WALLET["KRW"] < BUY_AMOUNT:
        print("❌ 잔액 부족")
        return

    volume = (BUY_AMOUNT * 0.9995) / price
    WALLET["KRW"] -= BUY_AMOUNT
    
    prev_vol = WALLET["COINS"].get(code, {"vol": 0})["vol"]
    prev_avg = WALLET["COINS"].get(code, {"avg": 0})["avg"]
    
    new_vol = prev_vol + volume
    new_avg = ((prev_vol * prev_avg) + (volume * price)) / new_vol
    
    WALLET["COINS"][code] = {"vol": new_vol, "avg": new_avg}
    
    save_wallet(WALLET) # 💾 매매할 때마다 자동 저장!
    
    msg = f"💎 [모의 매수] {code}\n가격: {price:,.0f}원\n수량: {volume:.4f}개\n잔액: {WALLET['KRW']:,.0f}원"
    print(msg)
    send_slack(msg)

def sell_coin(code, price):
    if code not in WALLET["COINS"] or WALLET["COINS"][code]["vol"] == 0:
        return
        
    volume = WALLET["COINS"][code]["vol"]
    avg_price = WALLET["COINS"][code]["avg"]
    profit_rate = ((price - avg_price) / avg_price) * 100
    sell_amount = (volume * price) * 0.9995
    
    WALLET["KRW"] += sell_amount
    WALLET["COINS"][code]["vol"] = 0
    WALLET["COINS"][code]["avg"] = 0
    
    save_wallet(WALLET) # 💾 매매할 때마다 자동 저장!
    
    icon = "🎉" if profit_rate > 0 else "💧"
    msg = f"{icon} [모의 매도] {code}\n매도가: {price:,.0f}원\n수익률: {profit_rate:.2f}%\n총 자산: {WALLET['KRW']:,.0f}원"
    print(msg)
    send_slack(msg)

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ 봇 가동! 현재 자산: {WALLET['KRW']:,.0f}원")
        
        subscribe_fmt = [
            {"ticket": "sniper-ticket"},
            {"type": "ticker", "codes": TARGETS, "isOnlyRealtime": True},
            {"format": "SIMPLE"}
        ]
        
        await websocket.send(json.dumps(subscribe_fmt))
        
        while True:
            try:
                data = await websocket.recv()
                data = json.loads(data)
                
                code = data['cd']
                price = data['tp']
                price_queues[code].append(price)
                
                if len(price_queues[code]) > 15:
                    rsi = calculate_rsi(list(price_queues[code]))
                    if rsi is None: continue
                    
                    current_time = time.time()
                    
                    # 🚦 RSI 기준값 조정 (테스트를 위해 좀 더 느슨하게 잡음)
                    # 매수: 30이하 / 매도: 70이상
                    if rsi <= 30 and (current_time - last_trade_time[code] > TRADE_COOLDOWN):
                        if WALLET["COINS"][code]["vol"] == 0:
                            buy_coin(code, price)
                            last_trade_time[code] = current_time

                    elif rsi >= 70 and WALLET["COINS"][code]["vol"] > 0:
                        sell_coin(code, price)
                        last_trade_time[code] = current_time
                        
                    # 로그는 100번 중 1번 정도만 출력 (터미널 도배 방지)
                    if rsi <= 35 or rsi >= 65:
                         print(f"[{code}] {price:,.0f}원 | RSI: {rsi:.1f}")

            except Exception as e:
                print(f"에러: {e}")
                await asyncio.sleep(1)
                break 

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(upbit_ws_client())
        except KeyboardInterrupt:
            print("\n종료합니다.")
            break
        except Exception as e:
            time.sleep(3)