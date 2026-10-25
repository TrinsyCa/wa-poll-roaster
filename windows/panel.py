"""Print the named UIA elements whose centre X lies in [minX, maxX] (debug helper).
usage: panel.py <minX> <maxX>"""
import sys
import ctypes
import comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(ctypes.windll.user32.FindWindowW(None, 'WhatsApp'))
a = win.FindAll(U.TreeScope_Descendants, uia.CreateTrueCondition())
seen = set()
for i in range(a.Length):
    e = a.GetElement(i); r = e.CurrentBoundingRectangle; n = e.CurrentName
    cx = (r.left + r.right) / 2
    key = (n, r.left, r.top)
    if int(sys.argv[1]) <= cx <= int(sys.argv[2]) and key not in seen:
        seen.add(key)
        print(e.CurrentLocalizedControlType, '|', repr(n[:80]), '|', r.left, r.top, r.right, r.bottom)
