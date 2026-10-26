"""Read actual cached source metadata; never submit fictional observations."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from public_sources import PublicSources

# This reads successful prior source responses. For a real network refresh run
# python refresh_sources.py from Terminal; that command may take a few seconds.
cache=Path(__file__).resolve().parents[1]/'data/public-cache'
for name,item in PublicSources(cache).snapshot().items():
    print(name, 'fresh:', item['fresh'], 'source:', item['url'])
    print('Successful fetch:', item.get('fetched_at'), 'error:', item.get('error'))
    if name=='events':
        for event in item.get('data') or []:
            print(event['title'],event['starts_at'],event['location'])
