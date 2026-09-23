import urllib.request, re
req = urllib.request.Request('http://musicfamily.org/realm/R40-R46/', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
matches = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)
for m in sorted(list(set(matches))):
    if any(k in m for k in ['R16', 'R20', 'R3', 'Merc', 'Research']):
        print(m)
