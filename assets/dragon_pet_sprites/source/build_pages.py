import json, os, sys
OUT = sys.argv[1]
idx = json.load(open(f'{OUT}/index.json'))
data = dict(clips=idx['clips'],
            lottie={c['name']: json.load(open(f"{OUT}/{c['lottie']}")) for c in idx['clips']},
            svg={c['name']: open(f"{OUT}/{c['svg']}").read() for c in idx['clips']})
blob = json.dumps(data, separators=(',', ':')).replace('</', '<\\/')
tpl = open('page_template.html').read().replace('__DATA__', blob)
lib = open('node_modules/lottie-web/build/player/lottie.min.js').read().replace('</script', '<\\/script')
head = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
local = tpl.replace('<script src="__LOTTIE_SRC__"></script>', '<script>' + lib + '</script>')
page = head + local + '\n</html>\n'
page = page.replace('<title>', '<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)} body{margin:0} [hidden]{display:none!important}</style>\n<title>', 1)
open(f'{OUT}/preview.html', 'w').write(page)
demo = page.replace("show(location.hash === '#cursor' ? 'cursor' : 'clips');\n</script>", "if (!location.hash) location.hash = 'cursor';\nshow(location.hash === '#cursor' ? 'cursor' : 'clips');\n</script>")
assert demo != page
open(f'{OUT}/cursor_demo.html', 'w').write(demo)
art = tpl.replace('__LOTTIE_SRC__', 'https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js')
open('artifact_preview.html', 'w').write(art)
for f in (f'{OUT}/preview.html', f'{OUT}/cursor_demo.html', 'artifact_preview.html'): print(f, os.path.getsize(f) // 1024, 'KB')
