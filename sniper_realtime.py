import asyncio
import websockets
import json
from collections import deque  # <--- 핵심: 데이터를 담을 그릇
from datetime import datetime

# 감시할 코인
TARGET_CODE = "KRW-BTC"

# 최근 가격 15개를 저장할 큐(Queue) 생성 (꽉 차면 옛날 데이터 자동 삭제)
price_queue = deque(maxlen=15)

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ [{TARGET_CODE}] 실시간 이동평균 감시 시작...")
        
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
                
                # 데이터 파싱
                price = data['tp'] # 현재가
                
                # 1. 큐에 현재 가격 저장
                price_queue.append(price)
                
                # 2. 이동평균 계산 (데이터가 어느 정도 모였을 때만)
                if len(price_queue) == price_queue.maxlen:
                    avg_price = sum(price_queue) / len(price_queue) # 평균가
                    diff = price - avg_price # 현재가 - 평균가
                    
                    # 3. 판단 로직 (골든크로스/데드크로스 흉내)
                    status = "보합 ➡️"
                    if diff > 0:
                        status = "상승 📈" # 평균보다 비싸짐
                    elif diff < 0:
                        status = "하락 📉" # 평균보다 싸짐
                        
                    now = datetime.now().strftime("%H:%M:%S")
                    print(f"[{now}] 현재가: {price:,.0f} | 평균가: {avg_price:,.0f} | {status} (차이: {diff:,.0f})")
                
                else:
                    print(f"데이터 모으는 중... ({len(price_queue)}/15)")

            except Exception as e:
                print(f"에러: {e}")
                break

if __name__ == "__main__":
    try:
        asyncio.run(upbit_ws_client())
    except KeyboardInterrupt:
        print("\n종료합니다.")