"""Fetch the licensed upstream Google Fonts sources and make static font instances."""
import base64
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1] / 'shared_workspace' / 'fonts'
SOURCES = [
    ('inter', 'Inter[opsz,wght].ttf', 'Inter-ExtraBold.ttf', {'wght': 800, 'opsz': 14}),
    ('instrumentserif', 'InstrumentSerif-Italic.ttf', 'InstrumentSerif-Italic.ttf', None),
    ('jetbrainsmono', 'JetBrainsMono[wght].ttf', 'JetBrainsMono-Medium.ttf', {'wght': 500}),
]
def fetch(path):
    request = Request('https://api.github.com/repos/google/fonts/contents/' + quote(path), headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'cinema-forge'})
    with urlopen(request) as response:
        return base64.b64decode(json.load(response)['content'])

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for family, source, target, axes in SOURCES:
        path = ROOT / target
        path.write_bytes(fetch(f'ofl/{family}/{source}'))
        if axes:
            font = TTFont(path)
            instantiateVariableFont(font, axes, inplace=True)
            font.save(path)
        (ROOT / f'{family}-OFL.txt').write_bytes(fetch(f'ofl/{family}/OFL.txt'))
if __name__ == '__main__': main()
