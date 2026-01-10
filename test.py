import yfinance as yf

# 애플(AAPL) 주식 데이터 가져오기
print("데이터를 가져오는 중입니다... (잠시만 기다려주세요)")
try:
    stock = yf.Ticker("AAPL")
    # 현재 가격 정보 가져오기
    info = stock.fast_info
    price = info['last_price']
    
    print("-" * 30)
    print(f"🍎 애플(AAPL) 현재 주가: ${price:.2f}")
    print("-" * 30)
    print("✅ 통신 성공! 데이터가 정상적으로 수신되었습니다.")
except Exception as e:
    print(f"❌ 오류 발생: {e}")