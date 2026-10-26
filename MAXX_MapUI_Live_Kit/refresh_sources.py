"""One public-source refresh for diagnosis. The server also refreshes every 15min."""
from pathlib import Path
from public_sources import PublicSources
s=PublicSources(Path(__file__).resolve().parent/'data/public-cache')
s.refresh()
for name,item in s.snapshot().items():
    print(name, 'CONNECTED' if item['fresh'] else 'UNAVAILABLE', item.get('fetched_at'), item.get('error'))
