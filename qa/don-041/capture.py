import subprocess,time,pathlib,xml.etree.ElementTree as ET
out=pathlib.Path("screenshots");out.mkdir(exist_ok=True)
def adb(*a):return subprocess.check_output(["adb",*a])
def capture(name):
 (out/(name+".png")).write_bytes(adb("exec-out","screencap","-p"))
 try:
  adb("shell","uiautomator","dump","/sdcard/window.xml")
  raw=adb("exec-out","cat","/sdcard/window.xml");(out/(name+".xml")).write_bytes(raw)
  return ET.fromstring(raw)
 except Exception:return None
adb("shell","wm","size","1080x1920")
adb("shell","wm","density","420")
adb("shell","am","start","-n","ru.citycontrol.don/.MainActivity")
time.sleep(25)
for i in range(12):
 root=capture("screen-%02d"%i)
 if root is not None:
  for n in root.iter("node"):
   text=n.attrib.get("text","")
   if "Данные и приложение" in text:
    import re
    b=list(map(int,re.findall(r"\d+",n.attrib.get("bounds",""))))
    if len(b)==4 and b[3]>b[1] and b[1]>0 and b[3]<1920:
     adb("shell","input","tap",str((b[0]+b[2])//2),str((b[1]+b[3])//2));time.sleep(2)
     capture("details-%02d"%i)
 adb("shell","input","swipe","540","1600","540","550","550");time.sleep(3)
capture("bottom")
