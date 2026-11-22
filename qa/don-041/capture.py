import subprocess,time,pathlib,xml.etree.ElementTree as ET,re
out=pathlib.Path("screenshots");out.mkdir(exist_ok=True)
def adb(*a):return subprocess.check_output(["adb",*a])
def capture(name):
 (out/(name+".png")).write_bytes(adb("exec-out","screencap","-p"))
 try:
  adb("shell","uiautomator","dump","/sdcard/window.xml")
  raw=adb("exec-out","cat","/sdcard/window.xml");(out/(name+".xml")).write_bytes(raw)
  return ET.fromstring(raw)
 except Exception:return None
def taptext(root,part):
 if root is None:return False
 for n in root.iter("node"):
  if part in n.attrib.get("text",""):
   b=list(map(int,re.findall(r"\d+",n.attrib.get("bounds",""))))
   if len(b)==4 and b[3]>b[1] and b[1]>63 and b[3]<1857:
    adb("shell","input","tap",str((b[0]+b[2])//2),str((b[1]+b[3])//2));time.sleep(2);return True
 return False
adb("shell","wm","size","1080x1920")
adb("shell","wm","density","420")
adb("shell","am","start","-n","ru.citycontrol.don/.MainActivity")
time.sleep(25)
opened=False
for i in range(18):
 root=capture("screen-%02d"%i)
 if not opened and taptext(root,"Данные и приложение"):
  opened=True
  root=capture("details")
 if opened and taptext(root,"Политика конфиденциальности"):
  capture("privacy");break
 adb("shell","input","swipe","20","1500","20","800","600");time.sleep(3)
capture("bottom")
