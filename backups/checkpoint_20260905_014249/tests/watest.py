import pygetwindow as gw

windows = gw.getAllTitles()
for w in windows:
    if w:
        print(w)
