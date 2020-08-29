# pyeditor
A curses text editor written in Python.

![pyeditor](https://github.com/eksd3/pyeditor/blob/master/pyeditor.png)

## Running
To run, simply execute pyeditor.py and optionally supply a filename:
```
python pyeditor.py /path/to/file
```

## Dependencies
pyeditor needs the curses module to work.
If you're on Windows you need windows-curses (Linux ditros should come with curses installed by default):
```
pip install windows-curses
```
Also, it optionally uses pyperclip for acessing the system clipboard:
```
pip install pyperclip
```
If pyperclip is not found clipboard functions will not work.

## Help
You can press 'H' to access the help window.

## Bugs
Pyeditor currently does not support terminal window resizing.
