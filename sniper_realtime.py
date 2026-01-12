import asyncio
import websockets
import json
from datetime import datetime

# 감시할 코인 목록 (원화 마켓)
target_codes = ["KRW-BTC", "KRW-ETH", "KRW-XRP"]

async def upbit_ws_client():
    uri = "wss://api.upbit.com/websocket/v1"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ 업비트 서버 연결 성공! 감시 대상: {target_codes}")
        
        # 1. 원하는 데이터 요청 (구독 신청)
        subscribe_fmt = [
            {"ticket": "sniper-ticket"},
            {"type": "ticker", "codes": target_codes, "isOnlyRealtime": True},
            {"format": "SIMPLE"} # 간소화된 응답 포맷
        ]
        
        # JSON으로 변환해서 서버로 전송
        await websocket.send(json.dumps(subscribe_fmt))
        
        # 2. 데이터 무한 수신 루프
        while True:
            try:
                data = await websocket.recv()
                data = json.loads(data) # JSON 파싱
                
                # 데이터 추출
                code = data['cd']           # 종목 코드 (예: KRW-BTC)
                price = data['tp']          # 현재가 (Trade Price)
                change = data['scr']        # 등락률 (Signed Change Rate)
                
                # 시간 찍기
                now = datetime.now().strftime("%H:%M:%S")
                
                # 색깔 입히기 (상승:빨강, 하락:파랑 - 터미널 설정에 따라 다를 수 있음)
                # 윈도우 기본 터미널에선 특수문자 깨질 수 있으니 단순 텍스트로
                print(f"[{now}] 🚀 {code} : {price:,.0f}원 ({change*100:.2f}%)")
                
            except Exception as e:
                print(f"❌ 에러 발생: {e}")
                break

# 비동기 실행 진입점
if __name__ == "__main__":
    try:
        asyncio.run(upbit_ws_client())
    except KeyboardInterrupt:
        print("\n🛑 프로그램을 종료합니다.")