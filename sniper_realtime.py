import asyncio
import websockets
import json
import csv  # <--- 추가됨: 엑셀 파일 처리를 위한 라이브러리
import os   # <--- 추가됨: 파일이 있는지 없는지 확인용
from collections import deque
from datetime import datetime

TARGET_CODE = "KRW-BTC"
price_queue = deque(maxlen=15)
LOG_FILE = "sniper_log.csv" # 저장할 파일 이름

# 💾 CSV 저장 함수 (블랙박스 기록)
def save_to_csv(timestamp, price, avg_price, diff, status):
    file_exists = os.path.isfile(LOG_FILE)
    
    # 'a' 모드: 덮어쓰지 않고 뒤에 계속 이어붙이기 (Append)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8-sig') as file:
        writer = csv.writer(file)
        
        # 파일이 처음 생길 때만 맨 윗줄(헤더) 작성
        if not file_exists:
            writer.writerow(["시간", "현재가", "이동평균", "차이", "상태"])
            
        writer.writerow([timestamp, price, avg_price, diff, status])

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ [{TARGET_CODE}] 기록을 시작합니다... (파일명: {LOG_FILE})")
        
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
                    if diff > 0: status = "상승"
                    elif diff < 0: status = "하락"
                        
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 1. 화면 출력
                    print(f"[{now}] {price:,.0f}원 | {status} (이격: {diff:,.1f}) -> 기록됨 💾")
                    
                    # 2. 파일 저장 (여기가 핵심!)
                    save_to_csv(now, price, avg_price, diff, status)
                
            except Exception as e:
                print(f"에러: {e}")
                break

if __name__ == "__main__":
    try:
        asyncio.run(upbit_ws_client())
    except KeyboardInterrupt:
        print("\n종료합니다.")