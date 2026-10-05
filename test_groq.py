import os
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))

try:
    # Send a fast message through the MoE pipeline
    response = client.chat.completions.with_raw_response.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": "Ping"}]
    )
    
    # Read the real-time server headers
    headers = response.headers
    
    # 🌟 ADD THESE TWO LINES INSIDE YOUR CODE TO SEE THE OUTPUT 🌟
    print("\n--- GROQ API METRICS ---")
    print(f"⏰ Token Quota Refreshing in: {headers.get('x-ratelimit-reset-tokens')}")
    print(f"📊 Remaining Daily Requests (RPD): {headers.get('x-ratelimit-remaining-requests')}")
    print(f"💡 Remaining Daily Tokens (TPD): {headers.get('x-ratelimit-remaining-tokens')}")

except Exception as e:
    # If you are already rate-limited, the countdown string will print here
    print(f"🛑 Blocked! Error details: {e}")
