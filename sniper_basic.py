import yfinance as yf
import time
from datetime import datetime

# 감시할 종목과 목표가 설정
TICKER = "AAPL"
TARGET_PRICE = 260.00  # 목표 가격 (이 가격 넘으면 알림)

print(f"🔭 [{TICKER}] 감시를 시작합니다... (목표가: ${TARGET_PRICE})")
print("-" * 50)

try:
    while True:
        # 1. 데이터 가져오기
        stock = yf.Ticker(TICKER)
        price = stock.fast_info['last_price']
        
        # 2. 현재 시간 확인
        now = datetime.now().strftime("%H:%M:%S")
        
        # 3. 판정 로직 (Sniper Logic)
        msg = ""
        if price >= TARGET_PRICE:
            msg = "🔥🔥🔥 목표가 도달! 매도하세요! 🔥🔥🔥"
            # 나중에는 여기서 카톡/슬랙 메시지를 보내거나 매도 주문을 넣습니다.
        else:
            msg = "대기 중..."

        # 4. 결과 출력
        print(f"[{now}] 현재가: ${price:.2f} | {msg}")
        
        # 5. 잠시 쉬기 (3초) - 너무 자주 요청하면 차단당할 수 있음
        time.sleep(3)

except KeyboardInterrupt:
    print("\n🛑 감시를 종료합니다.")