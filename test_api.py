from hithink import Client

API_KEY = "sk-fuyao-poRiDItUZBZc8QGg-P-H2lj0HhAGg4PN"

client = Client(API_KEY)
data = client.get_a_share_kline(
    code="600519.SH",
    period="daily",
    start_date="2025-08-01",
    end_date="2025-09-05"
)
print(data)
