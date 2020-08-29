import curses
from curses.textpad import Textbox
from os.path import isfile
from sys import modules, argv
import io

try:
    import pyperclip
except ImportError:
    print("Warning: Module 'pyperclip' failed to load.")
    print("Warning: Clipboard functions might not work correctly.")

ver = '1.0'

def imported(modname):
    return modname in modules

class TextBuffer(object):
    """
    Basic object for storing text
    """
    def __init__(self, text):
        self.lines = text.split('\n')

    def get_lines(self):
        return self.lines

    def get_line(self, i):
        return self.lines[i]

    def get_plaintext(self):
        text = ''
        for line in self.lines:
            if len(line) == 1:
                text += '\n'
            else:
                text += line
        return text

    def get_sel(self, sel):
        """
        Takes a Selection object as input
        Returns text from self.lines in plaintext
        """
        sr, sc = sel.get_start()
        er, ec = sel.get_end()
        text = ''

        if sr == er:
            # if the selection spans only one line:
            text = self.lines[sr][sc:ec]
        elif sr < er:
            text = text + self.lines[sr][sc:]
            for i in range(sr+1, er-1):
                text = text + self.lines[i]
            text = text + self.lines[er][:ec]
        return text

    def set_text(self, r1, c1, r2, c2, text):
        if self.is_valid(r1, c1) and self.is_valid(r2, c2):
            line = self.lines[r1][:c1] + text + self.lines[r2][c2:]
            self.lines[r1:r2+1] = line.split('\n')

    def is_valid(self, r, c):
        """
        Returns True if a point defined by (r, c) is valid
        """
        if r < 0 or r > len(self.lines) - 1:
            return False;
        cr = self.lines[r]
        if c < 0 or c > len(cr):
            return False;
        return True;

class Selection(object):
    """
    Struct to hold the starting and ending coordinates of
    the current selection
    """
    def __init__(self, r1=-1, c1=-1, r2=-1, c2=-1):
        self.r1 = r1
        self.c1 = c1
        self.r2 = r2
        self.c2 = c2

    def clear(self):
        self.r1 = -1
        self.c1 = -1
        self.r2 = -1
        self.c2 = -1

    def get_start(self):
        return self.r1, self.c1

    def get_end(self):
        return self.r2, self.c2

    def set_start(self, r, c):
        self.r1 = r
        self.c1 = c

    def set_end(self, r, c):
        self.r2 = r
        self.c2 = c

    def is_empty(self):
        return (self.r1 == -1 and self.r2 == -1 and \
                self.c1 == -1 and self.c2 == -1)

    def selected(self, r, c):
        """
        Returns True if a point (r, c) is currently
        selected
        """
        if r >= self.r1 and r < self.r2:
            return True
        elif r == self.r2:
            if c >= self.c1 and c < self.c2:
                return True
        return False

class EdState(object):
    """
    Struct to hold row, column, top, bottom, left and right
    so the cursor position of the editor can be properly restored
    when switching from help to normal mode
    """
    def __init__(self, ed):
        self._row = ed.row
        self._col = ed.col + ed.line_x
        self._top = ed.top
        self._bottom = ed.bottom
        self._left = ed.left
        self._right = ed.right

    def update(self, ed):
        self._row = ed.row
        self._col = ed.col + ed.line_x
        self._top = ed.top
        self._bottom = ed.bottom
        self._left = ed.left
        self._right = ed.right

    def restore(self, ed):
        ed.row = self._row
        ed.col = self._col - ed.line_x
        ed.top = self._top
        ed.bottom = self._bottom
        ed.left = self._left
        ed.right = self._right

class Editor(object):
    """
    The class for the editor
    Takes curses stdscr and an optional filename
    If filename is not supplied opens an empty buffer
    """
    def __init__(self, stdscr, filename=None):
        self.stdscr = stdscr
        self.filename = filename
        text = self.read_from_file(filename)
        # Buffers
        self.text_buf = TextBuffer(text)
        self.copy_buf = TextBuffer('')
        self.help_buf = self.init_helpbuf()
        self.curr_buf = self.text_buf # Current active buffer
        # /Buffers
        self.sel = Selection()
        self.row = 0
        self.col = 0
        self.run = True
        self.mode = 'normal'
        size = self.stdscr.getmaxyx()
        self.width = size[1]
        self.height = size[0]
        # Status bar color
        self.status_cl = curses.color_pair(1)
        # First and last lines that are shown
        self.top = 0
        self.bottom = self.height - 1
        # The width of the line numbering column
        self.line_x = 5
        # First and last column
        self.left = 0
        self.right = self.width - 1 - self.line_x
        # Tab length (n spaces)
        self.tablen = 4
        self.state = EdState(self)

    def mode_norm(self):
        # Set to normal mode
        self.mode = 'normal'
        self.cur_buf = self.text_buf
        self.status_cl = curses.color_pair(1)

    def mode_ins(self):
        # Set to insert mode
        self.mode = 'insert'
        self.curr_buf = self.text_buf
        self.status_cl = curses.color_pair(2)

    def mode_help(self):
        # Set to help mode
        self.mode = 'help'
        self.curr_buf = self.help_buf
        self.status_cl = curses.color_pair(3)
        self.state.update(self)
        self.row = 0
        self.col = 5
        self.top = 0
        self.bottom = self.height - 1

    def read_from_file(self, filename):
        text = ''
        if filename != None and isfile(filename):# os.path.isfile(filename):
            f = io.open(filename, mode="r", encoding="utf-8")
            text = f.read()
            f.close()
        return text

    def save_to_file(self):
        try:
            f = io.open(self.filename, mode="w", encoding="utf-8")
            f.write('\n'.join(self.text_buf.get_lines()))
            f.close()

        except IOError as err:
            errmes = "Failed to write to file '" + self.filename + "'; IOError."
            print(errmes)
            if not f.closed:
                f.close()

    def open_inputwin(self):
        """
        Show a textbox to input a file name
        Returns the filename as a string
        """
        def validator(key):
            if chr(key) == '\n': # Enter to confirm
                key = 7
            return key

        rows = 1
        cols = self.width - 3
        y = self.height - 2
        x = 1
        inputwin = curses.newwin(rows, cols, y, x)
        promptstr = 'Save as:> '
        inputwin.addstr(promptstr)
        inputwin.refresh()

        cols = self.width - 3 - len(promptstr)
        x = len(promptstr) + 1
        inputbox_win = curses.newwin(rows, cols, y, x)

        inputbox = Textbox(inputbox_win)
        inputbox.edit(validator)
        filename = inputbox.gather()

        # Clean up after confirming
        del inputbox_win
        del inputwin

        if filename == '':
            return self.filename
        return filename

    def init_helpbuf(self):
        global ver
        text = '\n~ PyED ~ ' + ver + '\n\n\
    Normal mode commands:\n\
               q : Quit\n\
               H : Toggle help\n\
      h, j, k, l : Cursor movement\n\
               $ : Move cursor to EOL\n\
               0 : Move cursor to the beginning of line\n\
               i : Insert mode\n\
               a : Insert mode after current cursor position\n\
               A : Insert mode at the EOL\n\
               L : Add to selection and move the cursor to the right\n\
               H : Add to selection and move the cursor to the left\n\
               V : Add the current line to selection\n\
               D : Deselect\n\
               y : Yank selection\n\
               p : Paste selection\n\
               Y : Yank to clipboard (if pyperclip is loaded)\n\
               P : Paste from clipboard (if pyperclip is loaded)\n\
               w : Write to file\n\
               W : Save as\n\
               g : Scroll to top\n\
               G : Scroll to bottom'

        return TextBuffer(text)

    def cmp_scroll_vert(self):
        """
        Compare self.row to self.top and self.bottom and
        scroll if neccessary
        """
        if self.row < self.top: # Should scroll up
            diff = self.top - self.row
            self.scroll_up(diff)
        elif self.row > self.bottom - 1: # Should scroll down
            diff = self.row - self.bottom
            self.scroll_down(diff + 1)

    def cmp_scroll_horiz(self):
        if self.col > self.right:
            diff = self.col - self.right
            self.scroll_right(diff)
        elif self.col < self.left + self.line_x:
            diff = self.left + self.line_x - self.col
            self.scroll_left(diff)

    def cmp_scroll(self):
        self.cmp_scroll_vert()
        self.cmp_scroll_horiz()

    def scroll_up(self, n):
        if self.top > 0:
            self.top -= n
            self.bottom -= n

    def scroll_down(self, n):
        if self.bottom < len(self.curr_buf.get_lines()):
            self.top += n
            self.bottom += n

    def scroll_left(self, n):
        if (self.left - n) >= 0:
            self.left -= n
            self.right -= n
        else:
            self.left = 0
            self.right = self.width - 1

    def scroll_right(self, n):
        self.right += n
        self.left += n

    def print_text(self, xpos, ypos, width, height):
        y = 0
        for i in range(self.top, self.top + self.height - 1):
            try:
                self.stdscr.addstr(y, 0, str(i))
                curr_line = self.curr_buf.get_line(i) + '\n'
                println = curr_line[self.left : self.right - self.line_x]
                # self.stdscr.addstr(y, self.line_x, println_2)

                for col, ch in enumerate(println):
                    if self.sel.selected(i, col):
                        self.stdscr.addstr(y, col + self.line_x, ch, curses.A_REVERSE)
                    else:
                        self.stdscr.addstr(y, col + self.line_x, ch)

                # Print '...' if the line is cut off on the right
                if self.right - self.line_x < len(curr_line) - 1:
                    self.stdscr.addstr(y, self.width - 4, '...')
                y += 1

            except:
                """ Either filled up the screen or there are
                no more lines to draw """
                break

    def inschar(self, ch):
        # Insert a character
        inscol = self.col - self.line_x
        self.text_buf.set_text(self.row, inscol, self.row, inscol, chr(ch))

        if chr(ch) == '\n':
            self.row += 1
            self.col = self.line_x
            self.cmp_scroll()
        else:
            self.move_cursor_right(1)

    def instab(self):
        # Insert a tabulator
        col = self.col - self.line_x
        diff = self.tablen - (col % self.tablen)
        tab = diff * ' '
        self.text_buf.set_text(self.row, col, self.row, col, tab)
        self.move_cursor_right(diff)

    def delchar(self):
        # Delete a character
        if self.col == self.line_x:
            if self.row == 0:
                # Delete the first char in the doc
                self.text_buf.set_text(0, 0, 0, 1, '')
            else:
                # Cursor is at the beginning of a line
                prev = self.text_buf.get_line(self.row - 1)
                curr = self.text_buf.get_line(self.row)

                self.move_cursor_left(1)
                self.text_buf.set_text(self.row, 0, self.row + 1, len(curr), prev + curr)
        else:
            # Cursor is not at the beginning of a line so delete a character like normal
            begincol = self.col - 1 - self.line_x
            endcol = begincol + 1
            self.text_buf.set_text(self.row, begincol, self.row, endcol, '')
            self.move_cursor_left(1)

    def update_scr(self):
        self.stdscr.clear()
        self.print_text(0, 0, self.height, self.width - 1)
        self.draw_status(0, self.height - 1)
        self.stdscr.move(self.row - self.top, self.col - self.left)
        self.stdscr.refresh()

    def draw_status(self, xpos, ypos):
        """ Draw the status line at the bottom """
        txt_mode = (' ' + self.mode).upper()
        txt_mode = '{}'.format(txt_mode).ljust(self.width - 2)
        self.stdscr.addstr(ypos, xpos + 1, txt_mode, self.status_cl)

        if self.filename != None:
            txt_filename = self.filename
        else:
            txt_filename = 'Empty Buffer'

        txt_cursorpos = '{} || {}:{}'.format(txt_filename, self.row + 1, self.col + 1 - self.line_x)
        self.stdscr.addstr(ypos, xpos + self.width - 1 - len(txt_cursorpos), txt_cursorpos, self.status_cl)

    def set_cursor_startpos(self):
        """
        Set self.row and self.col to the first nonblank character
        in the opened file
        Should only be used during init
        """
        line = self.curr_buf.get_line(0)
        for i, ch in enumerate(line):
            if ch != ' ':
                self.col = i + self.line_x
                return
        self.col = self.line_x

    def move_cursor_down(self, n):
        if self.row < len(self.curr_buf.get_lines()) - 1:
            self.row += n
            self.cmp_scroll()

    def move_cursor_up(self, n):
        if self.row > 0:
            self.row -= n
            self.cmp_scroll()

    def move_cursor_left(self, n):
        new_col = self.col - n
        if new_col < self.line_x and self.row > 0:
            self.row -= 1
            self.col = len(self.curr_buf.get_line(self.row)) + self.line_x
            self.cmp_scroll()
            return
        elif new_col >= self.line_x:
            self.col = new_col
            self.cmp_scroll_horiz()

    def move_cursor_right(self, n):
        try:
            new_col = self.col + n
            max_col = len(self.curr_buf.get_line(self.row)) + self.line_x
        except IndexError:
            # Reached EOF
            return

        if new_col > max_col:
            if self.row > len(self.curr_buf.get_lines()) - 1:
                return
            self.col = self.line_x
            self.row += 1
            self.cmp_scroll()
            return
        self.col = new_col
        self.cmp_scroll_horiz()

    def move_cursor_first_nonblank(self):
        """
        Move the cursor to the first nonblank
        character in the current line
        """
        for i, c in enumerate(self.text_buf.get_line(self.row)):
            if c != ' ':
                self.col = i + self.line_x
                self.cmp_scroll_horiz()
                return
        self.col = self.line_x
        self.cmp_scroll_horiz()

    def select_right(self):
        """
        Add current char to selection and move cursor left
        """
        if self.sel.is_empty():
            self.sel.set_start(self.row, self.col - self.line_x)
        self.move_cursor_right(1)
        self.sel.set_end(self.row, self.col - self.line_x)

    def select_left(self):
        """
        Add current char to selection and move cursor right
        """
        if self.sel.is_empty():
            self.sel.set_end(self.row, self.col - self.line_x)
        self.move_cursor_left(1)
        self.sel.set_start(self.row, self.col - self.line_x)

    def yank(self):
        if not self.sel.is_empty():
            buf = self.text_buf.get_sel(self.sel)
            self.copy_buf = TextBuffer(buf)
            self.sel.clear()

    def paste(self):
        cur_col = self.col - self.line_x
        buf = self.copy_buf.get_plaintext()
        self.text_buf.set_text(self.row, cur_col, self.row, cur_col, buf)
        self.move_cursor_right(len(buf))

    def yank_to_clip(self):
        if imported('pyperclip') and not self.sel.is_empty():
            buf = self.text_buf.get_sel(self.sel)
            pyperclip.copy(buf)
            self.sel.clear()

    def paste_from_clip(self):
        if imported('pyperclip'):
            cur_col = self.col - self.line_x
            buf = pyperclip.paste()
            self.text_buf.set_text(self.row, cur_col, self.row, cur_col, buf)

            # Move the cursor
            lines = buf.split('\n')
            if len(lines) == 1:
                self.move_cursor_right(len(lines[0]))
            else:
                self.col = len(lines[-1]) + self.line_x
                self.row += len(lines) - 1
            # self.scroll_down(len(lines) - 1)
            self.cmp_scroll()

    def scroll_to_top(self):
        self.scroll_up(self.top)
        self.scroll_left(self.left)
        self.row = self.top
        self.col = self.line_x

    def scroll_to_bottom(self):
        dist = len(self.text_buf.get_lines()) - self.bottom
        self.scroll_down(dist)
        self.scroll_left(self.left)
        self.row = len(self.text_buf.get_lines()) - 1
        self.col = self.line_x

    def event_handler_normal(self, ch):
        """ Handle keypresses from self.stdscr.getch() """

        if ch == ord('q'): # Quit
            self.run = False

        elif ch == ord('i'): # Enter insert mode
            self.mode_ins()

        elif ch == ord('a'): # Enter insert mode after current
            self.mode_ins()
            self.move_cursor_right(1)

        elif ch == ord('H'): # Enter help mode
            self.mode_help()

        # """ Cursor movement """
        elif ch == ord('j'):
            self.move_cursor_down(1)

        elif ch == ord('k'):
            self.move_cursor_up(1)

        elif ch == ord('h') or ch == 8:
            self.move_cursor_left(1)

        elif ch == ord('l'):
            self.move_cursor_right(1)

        elif ch == ord('A'): # Move to EOL and enter insert mode
            self.col = len(self.text_buf.get_line(self.row)) + self.line_x
            self.cmp_scroll_horiz()
            self.mode_ins()

        elif ch == ord('$'): # Move to EOL
            self.col = len(self.text_buf.get_line(self.row)) + self.line_x
            self.cmp_scroll_horiz()

        elif ch == ord('0'):
            self.move_cursor_first_nonblank()

        # """ Selection keys """
        elif ch == ord('L'):
            self.select_right()

        elif ch == ord('H'):
            self.select_left()

        elif ch == ord('V'): # Select the entire line
            self.sel.clear()
            self.sel.set_start(self.row, 0)
            self.sel.set_end(self.row, len(self.text_buf.get_line(self.row)))

        elif ch == ord('D') or ch == 27: # Deselect
            self.sel.clear()

        # """ Copying and pasting """
        elif ch == ord('y'): # Yank selection
            self.yank()

        elif ch == ord('p'): # Paste from self.copy_buf
            self.paste()

        elif ch == ord('Y'):
            self.yank_to_clip()

        elif ch == ord('P'):
            self.paste_from_clip()

        # """ File handling """
        elif ch == ord('w'): # Write to file
            if self.filename == None:
                self.filename = self.open_inputwin()
            self.save_to_file()

        elif ch == ord('W'): # Save as
            self.filename = self.open_inputwin()
            self.save_to_file()

        # """ Keys for scrolling """
        elif ch == ord('g'):
            self.scroll_to_top()

        elif ch == ord('G'):
            self.scroll_to_bottom()

    def event_handler_insert(self, ch):

        if ch == 27: # ESC : exit insert mode
            self.mode_norm()
            if self.col > self.line_x: self.col -= 1

        elif ch == 127 or ch == 8: # DEL or Backspace
            self.delchar()

        elif ch == 9: # TAB
            self.instab()

        else:
            self.inschar(ch)

    def event_handler_help(self, ch):

        if ch == 27 or ch == ord('H'): # Exit halp mode
            self.mode_norm()
            self.curr_buf = self.text_buf
            self.state.restore(self)
            self.cmp_scroll()

        elif ch == ord('q'):
            self.run = False

        # j and k scroll down and up in help mode
        elif ch == ord('j'):
            self.move_cursor_down(1)
            self.scroll_down(1)

        elif ch == ord('k'):
            self.move_cursor_up(1)
            self.scroll_up(1)

    def main(self):
        self.set_cursor_startpos()
        while self.run:
            self.update_scr()
            ch = self.stdscr.getch()

            if self.mode == 'normal':
                self.event_handler_normal(ch)
            elif self.mode == 'insert':
                self.event_handler_insert(ch)
            elif self.mode == 'help':
                self.event_handler_help(ch)

        # Clean up before shutting down
        curses.echo()
        curses.nocbreak()
        curses.endwin()

def init_curses():
    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.start_color()
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_GREEN)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLUE)
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_MAGENTA)
    return stdscr

def main():
    global ver
    if len(argv) > 1:
        filename = argv[1]
    else:
        filename = None
    ed = Editor(init_curses(), filename)
    ed.main()
    print("~ PyED " + ver + " ~");

if __name__ == '__main__':
    main()
