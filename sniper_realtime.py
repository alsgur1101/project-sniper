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

# 💰 [신규] 가상 지갑 설정
# 1,000만원으로 시작
WALLET = {
    "KRW": 10_000_000, 
    "COINS": {code: {"vol": 0.0, "avg": 0.0} for code in TARGETS}
}
BUY_AMOUNT = 1_000_000 # 한 번 살 때 100만원어치 매수

# 쿨타임 (너무 자주 사고팔지 않게)
last_trade_time = {code: 0 for code in TARGETS}
TRADE_COOLDOWN = 60 # 1분

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

# 💸 [신규] 매수 함수
def buy_coin(code, price):
    # 돈이 부족하면 패스
    if WALLET["KRW"] < BUY_AMOUNT:
        print("❌ 잔액 부족으로 매수 실패")
        return

    # 수수료(0.05%) 고려해서 매수량 계산
    volume = (BUY_AMOUNT * 0.9995) / price
    
    # 지갑 업데이트 (돈 나가고 코인 들어옴)
    WALLET["KRW"] -= BUY_AMOUNT
    
    # 평단가 재계산 (기존 보유량 + 신규 매수량)
    prev_vol = WALLET["COINS"][code]["vol"]
    prev_avg = WALLET["COINS"][code]["avg"]
    new_vol = prev_vol + volume
    new_avg = ((prev_vol * prev_avg) + (volume * price)) / new_vol
    
    WALLET["COINS"][code]["vol"] = new_vol
    WALLET["COINS"][code]["avg"] = new_avg
    
    msg = f"💎 [모의 매수] {code}\n가격: {price:,.0f}원\n수량: {volume:.4f}개\n잔액: {WALLET['KRW']:,.0f}원"
    print(msg)
    send_slack(msg)

# 💸 [신규] 매도 함수
def sell_coin(code, price):
    volume = WALLET["COINS"][code]["vol"]
    
    # 가진 게 없으면 패스
    if volume == 0: return
    
    # 수익률 계산
    avg_price = WALLET["COINS"][code]["avg"]
    profit_rate = ((price - avg_price) / avg_price) * 100
    
    # 매도 금액 (수수료 제외)
    sell_amount = (volume * price) * 0.9995
    
    # 지갑 업데이트
    WALLET["KRW"] += sell_amount
    WALLET["COINS"][code]["vol"] = 0
    WALLET["COINS"][code]["avg"] = 0
    
    icon = "🎉" if profit_rate > 0 else "💧"
    msg = f"{icon} [모의 매도] {code}\n매도가: {price:,.0f}원\n수익률: {profit_rate:.2f}%\n총 자산: {WALLET['KRW']:,.0f}원"
    print(msg)
    send_slack(msg)

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ 가상 매매 봇 가동! 시작 자산: {WALLET['KRW']:,.0f}원")
        send_slack(f"🏦 모의투자 시스템 가동 (시드: 1,000만원)")
        
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
                    
                    now = datetime.now().strftime("%H:%M:%S")
                    current_time = time.time()
                    
                    # 🚦 매매 전략 (RSI 기반)
                    # 1. 매수 (RSI 30 이하 & 쿨타임 지남 & 미보유 시)
                    if rsi <= 30 and (current_time - last_trade_time[code] > TRADE_COOLDOWN):
                        if WALLET["COINS"][code]["vol"] == 0: # 없을 때만 산다 (단순화)
                            buy_coin(code, price)
                            last_trade_time[code] = current_time

                    # 2. 매도 (RSI 70 이상 & 보유 중일 때)
                    elif rsi >= 70 and WALLET["COINS"][code]["vol"] > 0:
                        sell_coin(code, price)
                        last_trade_time[code] = current_time
                        
                    # 상태 출력 (가끔씩만)
                    if rsi <= 35 or rsi >= 65:
                        status = "🔥 과열" if rsi >= 65 else "❄️ 침체"
                        print(f"[{now}] {code} | {price:,.0f} | RSI:{rsi:.1f} | {status}")

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