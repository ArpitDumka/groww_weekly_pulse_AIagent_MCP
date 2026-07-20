import re
import requests

ua = "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"
url = "https://apps.apple.com/in/app/groww-stocks-mutual-fund-ipo/id1404871703"
text = requests.get(url, headers={"User-Agent": ua}, timeout=30).text

patterns = [
    r'"accessToken":"([^"]+)"',
    r'"access_token":"([^"]+)"',
    r'"token":"(eyJ[^"]+)"',
    r'content="(eyJ[^"]+)"',
    r'webToken":"([^"]+)"',
]
for pat in patterns:
    m = re.findall(pat, text)
    print(pat, len(m), m[0][:40] if m else "")
