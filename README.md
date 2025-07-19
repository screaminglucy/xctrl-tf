# xctrl-tf

This is python code to control a Yamaha TF mixer with a Behringer XTouch control surface in XCtrl/MC mode

Set the IP addresses correctly inside xctrlpy.py and then run xctrltf.py

To run on Raspberry Pi:
1. Create python venv `python -m venv .venv`
2. Install mido and keyboard `.venv/bin/python -m pip install mido` `.venv/bin/python -m pip install keyboard`
3. Run: `.venv/bin/python xctrltf.py` If you get a warning about permissions: `sudo .venv/bin/python xctrltf.py` 

To run automatically on Raspberry Pi:

1. Create .desktop file and place in ~/.config/AutoStart
2. Put the following in the desktop file:
```
[Desktop Entry]
Name=xctrltf
Exec=lxterminal -e ~/xctrl_tf/.venv/bin/python ~/xctrl_tf/xctrltf.py
Path=~/xctrl_tf/
Terminal=true
```
3. Make the file executable
4. Reboot

## Reference Material

* [Python Script Template](https://usa.yamaha.com/files/download/other_assets/0/1266290/Python_Script_Template_V100.zip) - Simple Python scripts from Yamaha
* [Companion Yamaha RCP module](https://github.com/bitfocus/companion-module-yamaha-rcp) - Many commands implemented that aren't documented in this!
* [XTouch-py project](https://github.com/thejoshtaylor/XTouch-py) - Some bugs but mostly works!
