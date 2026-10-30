import json, sys, os
OUT = sys.argv[1]
idx = json.load(open(f'{OUT}/index.json'))
data = {'clips': idx['clips'], 'lottie': {}, 'svg': {}}
for c in idx['clips']:
    data['lottie'][c['name']] = json.load(open(f"{OUT}/{c['lottie']}"))
    data['svg'][c['name']] = open(f"{OUT}/{c['svg']}").read()
blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'preview_template.html')).read()
page = tpl.replace('__DATA__', blob)
open(sys.argv[2], 'w').write(page)   # artifact body (skeleton added at publish)
standalone = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
              '<style>[hidden]{display:none!important}body{margin:0}</style></head><body>' + page + '</body></html>')
open(f'{OUT}/preview.html', 'w').write(standalone)
print('preview bytes', len(page))
