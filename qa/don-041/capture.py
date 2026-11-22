import subprocess,time,pathlib,xml.etree.ElementTree as ET,re
out=pathlib.Path("screenshots");out.mkdir(exist_ok=True)
def adb(*a):return subprocess.check_output(["adb",*a])
def capture(name):
 (out/(name+".png")).write_bytes(adb("exec-out","screencap","-p"))
 adb("shell","uiautomator","dump","/sdcard/window.xml")
 raw=adb("exec-out","cat","/sdcard/window.xml");(out/(name+".xml")).write_bytes(raw)
 return ET.fromstring(raw)
adb("shell","wm","size","1080x1920")
adb("shell","wm","density","420")
adb("shell","am","start","-n","ru.citycontrol.don/.MainActivity")
time.sleep(20)
capture("main")
for i in range(8):
 adb("shell","input","keyevent","93");time.sleep(2);capture("page-%02d"%i)
for i in range(8):
 adb("shell","input","keyevent","61","61","61");time.sleep(1);capture("focus-%02d"%i)
