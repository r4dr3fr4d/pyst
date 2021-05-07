#!/usr/bin/env python

from Xlib import X, display
from Xlib.XK import string_to_keysym, keysym_to_string

import pty, os, fcntl, termios, struct, select
import re

from code import interact
#from IPython import embed

font_name_ob    = "-adobe-courier-medium-o-normal--12-120-75-75-m-70-iso8859-1"
font_name_bd    = "-adobe-courier-bold-r-normal--12-120-75-75-m-70-iso8859-1"
font_name_bd_ob = "-adobe-courier-bold-o-normal--12-120-75-75-m-70-iso8859-1"
font_name       = "-adobe-courier-medium-r-normal--12-120-75-75-m-70-iso8859-1"
#font_name = "-adobe-courier-medium-*-normal--*"

# text states we need to maintain:
# character
# bold
# oblique (this and oblique could just be captured in the font perhaps?)
# underline
# blink
# fg
# bg
#
# so....a tuple?
# e.g.
# ('a', True, False, False, False, (0xaa, 0x10, 0x60), (0, 0, 0))
# or
# ('a', font, False, False, (0xaa, 0x10, 0x60), (0, 0, 0))

# colors
WHITE = 0xffffff
PINK  = 0xaa1060
BLACK = 0x000000
background_color = BLACK
 
# X11 setup

# let's use these for both
disp = display.Display()
screen = disp.screen()

# window init
window = screen.root.create_window(
    20, 20, 200, 200, 1,
    screen.root_depth,
    background_pixel = BLACK,
    event_mask = X.ExposureMask | X.KeyPressMask | X.KeyReleaseMask,
    )

# open a font
font = disp.open_font(font_name)
fq = font.query()

# this first width calculation doesn't seem to work...
#font_width = fq._data['max_bounds']['right_side_bearing'] - fq._data['min_bounds']['left_side_bearing']
font_width  = fq._data['min_bounds']['character_width']
font_height = fq._data['max_bounds']['ascent'] + fq._data['max_bounds']['descent']

'''
fq._data['min_bounds']['left_side_bearing']
fq._data['min_bounds']['right_side_bearing']
fq._data['min_bounds']['character_width']
fq._data['min_bounds']['ascent']
fq._data['min_bounds']['descent']
fq._data['max_bounds']
fq._data['font_ascent']
fq._data['font_descent']
'''

# create gc(s) with the colors we create
gc_background = window.create_gc(
    foreground = background_color,
    background = background_color,
    )

gc_text = window.create_gc(
    font = font,
    foreground = WHITE,
    background = background_color,
    )

window.map()

# end X11 setup

master, slave = os.openpty()

# get terminal size
win_sz = fcntl.ioctl(0, termios.TIOCGWINSZ, b'\x00' * 8)
win_sz = struct.unpack('HHHH', win_sz)

# set terminal size
#fcntl.ioctl(0, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

pid = os.fork()
if pid == 0:
    os.close(master)
    os.setsid()
    os.dup2(slave, 0)
    os.dup2(slave, 1)
    os.dup2(slave, 2)
    os.close(slave)
    os.execl("/bin/sh", "/bin/sh")

else:
    os.close(slave)

text = list()

x11_fd = disp.fileno()

# modifiers
modifier_mapping = disp.get_modifier_mapping()
modifier_dict = {}
nti = [('Shift', X.ShiftMapIndex),
       ('Control', X.ControlMapIndex), ('Mod1', X.Mod1MapIndex),
       ('Alt', X.Mod1MapIndex), ('Mod2', X.Mod2MapIndex),
       ('Mod3', X.Mod3MapIndex), ('Mod4', X.Mod4MapIndex),
       ('Mod5', X.Mod5MapIndex), ('Lock', X.LockMapIndex)]

for n, i in nti:
    modifier_dict[n] = list(modifier_mapping[i])
mod_state = 0


def redraw():
    #print("redraw")
    window.fill_rectangle(gc_background, 0, 0, win_geom.width, win_geom.height)
    #window.poly_text(gc_text, 0, font_height*(i+1), ''.join(text[i]))
    for i in range(0, len(text)):
        window.draw_text(gc_text, 0, font_height*(i+1), ''.join(text[i]))
    #for i in range(0, rows):
        #for j in range(0, cols):
            #window.draw_text(gc_text, font_width*j, font_height*(i+1), text[i][j])
    #disp.flush()
    disp.sync()


debug_text = b''

empty = ' '
#empty = '='
win_geom = window.get_geometry()
rows = win_geom.height // font_height
cols = win_geom.width  // font_width
text = [[empty] * cols for x in range(rows)]

cur_x = 0
cur_y = 0

# window loop
while True:
    #print("Continuing..")

    # problem: how do we model the current matrix of character cells?
    # how do we model changes to the window size?

    # get window geometry and re-determine term width/height
    # TODO:  update cur_x/cur_y as well
    win_geom = window.get_geometry()
    n_rows = win_geom.height // font_height
    n_cols = win_geom.width  // font_width
    n_text = [[empty] * n_cols for x in range(n_rows)]
    #for l in n_text: # to help in debugging
        #l[-1] = 'e'

    if n_rows != rows:
        print("rows, n_rows:", rows, n_rows)
        print("height, font_height:", win_geom.height, font_height)
    if n_cols != cols:
        print("cols, n_cols:", cols, n_cols)
        print("width, font_width:", win_geom.width, font_width)

    for i in range(min(rows, n_rows)):
        for j in range(min(cols, n_cols)):
            n_text[i][j] = text[i][j]

    text = n_text
    rows = n_rows
    cols = n_cols

    # set terminal size
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

    redraw()

    #print("select...")
    #ready_fds = select.select([master, x11_fd], [], [])
    #if master in ready_fds[0]:
    while master in select.select([master, x11_fd], [], [])[0]:
        #print("master...")
        if r := os.read(master, 1):
            # TODO: our terminal codes/emulation features will go here
            debug_text += r
            print(r)
            if r == b'\x1b': # ESC

                print("ESC")
                # continue reading until we complete the escape
                if (r := os.read(master, 1)) == b'[': # CSI
                    csi = bytes()
                    while r := os.read(master, 1):
                        csi += r
                        if not r or ord(r) in range(0x40, 0x7e):
                            break

                    #print("csi:", csi)

                    if csi == b'?2004h': # bracketed paste mode on
                        print("bracketed paste mode on")
                        pass

                    elif csi == b'?2004l': # bracketed paste mode off
                        print("bracketed paste mode off")
                        pass

                    elif csi == b'2J': # clear screen
                        text = [[empty] * n_cols for x in range(n_rows)]
                        cur_x = cur_y = 0

                    elif m := re.match(b'[012]?K', csi): # clear in line
                        if m.end() == 1 or csi[0] == b'0':
                            pass
                        elif csi[0] == b'1':
                            pass
                        elif csi[0] == b'2':
                            pass

                    elif m := re.match(b'[0-9;]*m', csi): # SGR
                        #print("SGR")
                        sgr = csi[:-1].split(b';')

                        if sgr[0] == b'1': # bold
                            pass
                        elif sgr[0] == b'3': # italic/oblique
                            pass
                        elif sgr[0] == b'4': # underline
                            pass
                        elif sgr[0] == b'30': # fg black
                            pass
                        elif sgr[0] == b'31': # fg red
                            pass
                        elif sgr[0] == b'32': # fg green
                            pass
                        elif sgr[0] == b'33': # fg yellow
                            pass
                        elif sgr[0] == b'34': # fg blue
                            pass
                        elif sgr[0] == b'35': # fg magenta
                            pass
                        elif sgr[0] == b'36': # fg cyan
                            pass
                        elif sgr[0] == b'37': # fg white
                            pass
                        elif sgr[0] == b'38': # set fg color
                            if sgr[1] == b'5': # 8-bit color
                                pass
                            elif sgr[1] == b'2': # 24-bit/true color
                                pass
                        elif sgr[0] == b'39': # default fg color
                            pass
                        elif sgr[0] == b'30': # bg black
                            pass
                        elif sgr[0] == b'31': # bg red
                            pass
                        elif sgr[0] == b'32': # bg green
                            pass
                        elif sgr[0] == b'33': # bg yellow
                            pass
                        elif sgr[0] == b'34': # bg blue
                            pass
                        elif sgr[0] == b'35': # bg magenta
                            pass
                        elif sgr[0] == b'36': # bg cyan
                            pass
                        elif sgr[0] == b'37': # bg white
                            pass
                        elif sgr[0] == b'38': # set bg color
                            if sgr[1] == b'5': # 8-bit color
                                pass
                            elif sgr[1] == b'2': # 24-bit/true color
                                pass
                        elif sgr[0] == b'39': # default bg color
                            pass

                    else:
                        print("couldn't decode csi:", csi)


            elif r == b'\x07': # BEL
                print("BEL")

            elif r == b'\x08': # BS
                text[cur_y][cur_x] = empty
                cur_x = max(cur_x - 1, 0)


            else: # add to our displayed text
                #print("add to text")
                # better way to do this than a try/except?
                try:
                    c = r.decode()
                    #print(c)
                except:
                    pass
                    #print("No decode")

                if c == '\r':
                    cur_x = 0

                elif c == '\t':
                    # tab behavior:
                    # - to next multiple of 8 spaces?
                    # - don't advance cursor past eol
                    cur_x = min(cur_x + (8 - cur_x % 8) , cols-1)

                else:
                    #print("not cr")
                    if c != '\n':
                        if cur_x >= cols:
                            cur_x = 0
                            if cur_y == len(text) - 1:
                                text.pop(0)
                                text += [[empty] * cols]
                            else:
                                cur_y += 1

                    else:
                        if cur_y == len(text) - 1:
                            text.pop(0)
                            text += [[empty] * cols]
                        else:
                            cur_y += 1
                        continue

                    if cur_y >= rows:
                        pass

                    try:
                        text[cur_y][cur_x] = c
                    except IndexError:
                        print("cur_y, cur_x:", cur_y, cur_x)
                        print("len(text):", len(text))
                        print("len(text[cur_y]):", len(text[cur_y]))
                        exit()

                    #print(''.join(text[cur_y]))
                    cur_x += 1

    #print("Read...")

    redraw()

    #if x11_fd in ready_fds[0]:
    while disp.pending_events():
        #print("Getting event..")

        e = disp.next_event()

        if e.type == X.Expose:
            redraw()

        elif e.type == X.KeyRelease:
            # update modifier state
            if e.detail in modifier_dict['Shift']:
                mod_state &= ~(1)

            elif e.detail in modifier_dict['Alt']:
                print("release alt")
                mod_state &= ~(2)

            elif e.detail in modifier_dict['Control']:
                pass

        elif e.type == X.KeyPress:
            #print("keypress")

            # update modifier state
            if e.detail in modifier_dict['Shift']:
                mod_state |= 1

            elif e.detail in modifier_dict['Alt']:
                print("alt")
                mod_state |= 2

            elif e.detail in modifier_dict['Control']:
                pass

            else:
                ks = disp.keycode_to_keysym(e.detail, mod_state)
                #print("ks num and string:")
                #print(ks)
                ls = disp.lookup_string(ks)
                #print(ls)

                if chr(ks) == 'q':
                    raise SystemExit

                elif chr(ks) == 'w':
                    interact(banner='Debug.', local=locals())
                    exit()

                # which of these do we need to do?
                #b = ks.to_bytes(1, 'big')
                #b = ks.to_bytes(2, 'big')
                #print(b)
                if ls:
                    os.write(master, ls.encode()) 

# next we should try....
#  - change font & size 
#  - italic/bold
#  - change colors (font, fg, bg)
#
#  - handle \r and \n
#  - handle wrapping
