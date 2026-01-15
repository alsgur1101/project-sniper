import asyncio
import websockets
import json
import csv
import os
import requests # <--- 추가됨: 슬랙 전송용
import time     # <--- 추가됨: 시간 계산용
from collections import deque
from datetime import datetime

TARGET_CODE = "KRW-BTC"
price_queue = deque(maxlen=15)
LOG_FILE = "sniper_log.csv"

# 1. 환경변수 파일(.env) 로드
load_dotenv()

# 2. 금고에서 URL 꺼내오기 (이제 소스코드에 주소가 노출되지 않습니다!)
SLACK_URL = os.getenv("SLACK_URL")

# 혹시 못 가져왔을 때를 대비한 안전장치
if not SLACK_URL:
    print("❌ 에러: .env 파일에서 SLACK_URL을 찾을 수 없습니다.")
    exit()

# ⏳ 알림 쿨타임 설정 (마지막 알림 보낸 시간 기억)
last_alert_time = 0 
ALERT_COOLDOWN = 60 # 60초 (1분에 한 번만 알림)

def send_slack(msg):
    """슬랙으로 메시지를 쏘는 함수"""
    try:
        payload = {"text": msg}
        requests.post(SLACK_URL, json=payload)
    except Exception as e:
        print(f"슬랙 전송 실패: {e}")

def save_to_csv(timestamp, price, avg_price, diff, status):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["시간", "현재가", "이동평균", "차이", "상태"])
        writer.writerow([timestamp, price, avg_price, diff, status])

async def upbit_ws_client():
    global last_alert_time # 전역 변수 사용
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ [{TARGET_CODE}] 스나이퍼 가동! (알림 대기 중...)")
        send_slack(f"🔫 [{TARGET_CODE}] 스나이퍼 봇이 가동되었습니다!") # 시작 알림 테스트
        
        subscribe_fmt = [
            {"ticket": "sniper-ticket"},
            {"type": "ticker", "codes": [TARGET_CODE], "isOnlyRealtime": True},
            {"format": "SIMPLE"}
        ]
        
        await websocket.send(json.dumps(subscribe_fmt))
        
        while True:
            try:
                data = await websocket.recv()
                data = json.loads(data)
                
                price = data['tp']
                price_queue.append(price)
                
                if len(price_queue) == price_queue.maxlen:
                    avg_price = sum(price_queue) / len(price_queue)
                    diff = price - avg_price
                    
                    status = "보합"
                    if diff > 0: status = "상승 📈"
                    elif diff < 0: status = "하락 📉"
                        
                    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now_str}] {price:,.0f}원 | {status} (이격: {diff:,.1f})")
                    save_to_csv(now_str, price, avg_price, diff, status)

                    # 🔔 알림 로직 (상승 추세이고 + 쿨타임이 찼을 때만)
                    # 테스트를 위해 '상승'일 때 무조건 알림이 가도록 설정했습니다.
                    current_time = time.time()
                    if "상승" in status and (current_time - last_alert_time > ALERT_COOLDOWN):
                        msg = f"🚀 [매수 신호] {TARGET_CODE}\n현재가: {price:,.0f}원\n이평선 돌파! ({diff:,.0f}원 차이)"
                        send_slack(msg)
                        print(">>> 📲 슬랙 알림 전송 완료!")
                        last_alert_time = current_time # 쿨타임 리셋

            except Exception as e:
                print(f"에러: {e}")
                break

if __name__ == "__main__":
    try:
        asyncio.run(upbit_ws_client())
    except KeyboardInterrupt:
        print("\n종료합니다.")