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

# 1. 환경변수 로드
load_dotenv()
SLACK_URL = os.getenv("SLACK_URL")

# 🎯 감시할 타겟 목록 (여러 개 추가 가능!)
TARGETS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"]

# 🗂️ 각 종목별로 데이터를 담을 '딕셔너리' 생성
# 구조: { "KRW-BTC": deque(...), "KRW-ETH": deque(...), ... }
price_queues = {code: deque(maxlen=50) for code in TARGETS}

# 쿨타임 관리 (종목별로 따로 관리해야 함!)
last_alert_times = {code: 0 for code in TARGETS}
ALERT_COOLDOWN = 60 

def send_slack(msg):
    if not SLACK_URL: return
    try:
        requests.post(SLACK_URL, json={"text": msg})
    except Exception as e:
        print(f"슬랙 전송 실패: {e}")

def calculate_rsi(prices, period=14):
    if len(prices) < period:
        return None
    series = pd.Series(prices)
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 1)
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ 멀티 타겟 스나이퍼 가동! 감시 대상: {len(TARGETS)}개")
        print(f"🎯 목록: {TARGETS}")
        send_slack(f"📡 멀티 스나이퍼 가동 시작! ({len(TARGETS)}개 종목 감시)")
        
        # 구독 요청 (코드를 리스트로 한 번에 보냅니다)
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
                
                # 1. 데이터 분류 (Demux)
                code = data['cd']       # 종목 코드 확인
                price = data['tp']      # 가격 확인
                
                # 해당 종목의 큐에 데이터 넣기
                price_queues[code].append(price)
                
                # 2. 분석 및 판단
                if len(price_queues[code]) > 15:
                    rsi = calculate_rsi(list(price_queues[code]))
                    
                    if rsi is not None:
                        now = datetime.now().strftime("%H:%M:%S")
                        
                        # 중요할 때만 출력 (너무 시끄러우니까)
                        # RSI가 35 이하(약세)거나 65 이상(강세)일 때만 로그 찍기
                        if rsi <= 35 or rsi >= 65:
                            status = "🔥 과열" if rsi >= 65 else "❄️ 침체"
                            print(f"[{now}] {code} | {price:,.0f}원 | RSI: {rsi:.1f} ({status})")
                        
                        # 🔔 알림 로직 (종목별 쿨타임 적용)
                        current_time = time.time()
                        if (rsi <= 30 or rsi >= 70) and (current_time - last_alert_times[code] > ALERT_COOLDOWN):
                            condition = "매수 기회 (과매도) 🟢" if rsi <= 30 else "매도 주의 (과매수) 🔴"
                            msg = f"🚨 [{code}] 신호 포착!\n현재가: {price:,.0f}원\nRSI: {rsi:.1f}\n상태: {condition}"
                            send_slack(msg)
                            last_alert_times[code] = current_time
                            print(f">>> 📲 {code} 슬랙 알림 전송!")

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
            print("재접속 중...")
            time.sleep(3)