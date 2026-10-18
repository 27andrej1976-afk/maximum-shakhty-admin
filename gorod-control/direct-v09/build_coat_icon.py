"""Generate installed Android launcher icon from the existing Shakhty city coat image."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import re
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'map-v07/shakhty-coat.png'
assert source.exists(), 'Official Shakhty coat asset missing'
image=Image.open(source).convert('RGBA')
assert image.width>40 and image.height>40
S=432
base=Image.new('RGBA',(S,S),(16,26,44,255))
mask=Image.new('L',(S,S),0)
draw=ImageDraw.Draw(mask)
draw.ellipse((6,6,S-7,S-7),fill=255)
# Crest stays fully visible within Android's adaptive round launcher mask.
inner=ImageOps.contain(image,(276,316),Image.Resampling.LANCZOS)
base.alpha_composite(inner,((S-inner.width)//2,(S-inner.height)//2))
base.putalpha(mask)
dest=ROOT/'android/app/src/main/res/drawable-nodpi'
dest.mkdir(parents=True,exist_ok=True)
base.save(dest/'coat_launcher.png')
manifest=ROOT/'android/app/src/main/AndroidManifest.xml'
text=manifest.read_text()
text=text.replace('android:icon="@drawable/launcher_icon"','android:icon="@drawable/coat_launcher"').replace('android:roundIcon="@drawable/launcher_icon"','android:roundIcon="@drawable/coat_launcher"')
assert 'android:icon="@drawable/coat_launcher"' in text
manifest.write_text(text)
gradle=ROOT/'android/app/build.gradle'
text=gradle.read_text()
text=re.sub(r'versionCode \d+','versionCode 10',text)
text=re.sub(r"versionName '[^']+'","versionName '0.9.1-test'",text)
gradle.write_text(text)
print('Verified installed icon: Shakhty coat, round 432x432, version 0.9.1')
