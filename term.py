#!/usr/bin/env python

from Xlib import X, display
from Xlib.XK import string_to_keysym, keysym_to_string

import pty, os, fcntl, termios, struct, time
from os import read, write
from select import select
from re import match

from functools import wraps
from code import interact

def main():
    # colors
    BLACK   = 0x000000
    RED     = 0xcd0000
    GREEN   = 0x00cd00
    YELLOW  = 0xcdcd00
    BLUE    = 0x0000ee
    MAGENTA = 0xcd00cd
    CYAN    = 0x00cdcd
    WHITE   = 0xffffff

    PINK    = 0xaa1060

    DEFAULT_FG = WHITE
    DEFAULT_BG = BLACK
     
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
    font_name       = "-adobe-courier-medium-r-normal--12-120-75-75-m-70-iso8859-1"
    font_name_bd    = "-adobe-courier-bold-r-normal--12-120-75-75-m-70-iso8859-1"
    font_name_ob    = "-adobe-courier-medium-o-normal--12-120-75-75-m-70-iso8859-1"
    font_name_bd_ob = "-adobe-courier-bold-o-normal--12-120-75-75-m-70-iso8859-1"

    font        = disp.open_font(font_name)
    font_q      = font.query()
    font_wd     = font_q._data['min_bounds']['character_width']
    font_ht     = font_q._data['max_bounds']['ascent'] + font_q._data['max_bounds']['descent']

    font_bd    = disp.open_font(font_name_bd)
    font_ob    = disp.open_font(font_name_ob)
    font_bd_ob = disp.open_font(font_name_bd_ob)


    window.map()

    # end X11 setup

    master, slave = os.openpty()

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

    s = 0

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


    # create gc(s) with the colors we create
    gc_background = window.create_gc(
        foreground = DEFAULT_BG,
        background = DEFAULT_BG
        )

    gc_text = window.create_gc(
        font = font,
        foreground = DEFAULT_FG,
        background = DEFAULT_BG
        )

    def redraw(blink=True):
        #print("redraw")
        #window.fill_rectangle(gc_background, 0, 0, win_geom.width, win_geom.height)
        prev_vals = (False, False, DEFAULT_FG, DEFAULT_BG) # these are just bold, oblique, and colors

        for i in range(0, rows):
            for j in range(0, cols):
                # check against previous graphics context 

                vals = text[i][j][3:]

                if vals != prev_vals: # change GCs
                    if vals[3] != prev_vals[3]:
                        gc_background.change(foreground = vals[3])

                    if vals[0] and vals[1]:
                        font_draw    = font_bd_ob
                    elif vals[1]:
                        font_draw    = font_ob
                    elif vals[0]:
                        font_draw    = font_bd
                    else:
                        font_draw    = font

                    gc_text.change(font = font_draw, foreground = vals[2])

                prev_vals = vals

                #window.fill_rectangle(gc_background, 0, 0, win_geom.width, win_geom.height)
                window.fill_rectangle(gc_background, font_wd*j, font_ht*(i+0), font_wd, font_ht)
                window.draw_text(gc_text, font_wd*j, font_ht*(i+1), text[i][j][0])

                if text[i][j][2]: # underline
                    pass

        disp.sync()


    debug_text = b''

    win_geom = window.get_geometry()
    rows = win_geom.height // font_ht
    cols = win_geom.width  // font_wd

    blink     = False
    bold      = False
    oblique   = False
    underline = False
    fg        = DEFAULT_FG
    bg        = DEFAULT_BG

    empty = (' ', blink, underline, bold, oblique, fg, bg)

    text = list()
    for i in range(0, rows):
        text.append(list())
        for j in range(0, cols):
            text[i].append(empty)

    cur_x = 0
    cur_y = 0


    # window loop
    while True:
        #print("Continuing..")

        win_geom = window.get_geometry()
        n_rows = win_geom.height // font_ht
        n_cols = win_geom.width  // font_wd

        n_text = list()
        for i in range(0, n_rows):
            n_text.append(list())
            for j in range(0, n_cols):
                n_text[i].append(empty)

        try:
            for i in range(min(rows, n_rows)):
                for j in range(min(cols, n_cols)):
                    n_text[i][j] = text[i][j]
        except IndexError:
            print(i, j)
            print(rows, cols, n_rows, n_cols)
            exit()

        rows = n_rows
        cols = n_cols
        text = n_text

        # set terminal size
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))

        ready_fds = select([master, x11_fd], [], [], 0) 
        if not ready_fds[0]:
            redraw()
        else:
            pass
            #print(master, x11_fd, ready_fds[0])

        #print("pre-block select")
        ready_fds = select([master, x11_fd], [], []) # blocking select
        while master in ready_fds[0]:
            #print("master...")
            if r := read(master, 1):
                #print("read...")

                debug_text += r
                #print(r)

                if r == b'\x1b': # ESC
                    #print("ESC")
                    # continue reading until we complete the escape
                    if (r := read(master, 1)) == b'[': # CSI
                        csi = bytes()
                        while r := read(master, 1):
                            csi += r
                            if not r or ord(r) in range(0x40, 0x7e):
                                break

                        #print("csi:", csi)

                        if csi == b'?2004h': # bracketed paste mode on
                            #print("bracketed paste mode on")
                            pass

                        elif csi == b'?2004l': # bracketed paste mode off
                            #print("bracketed paste mode off")
                            pass

                        elif csi == b'2J': # clear screen
                            #text = [[empty] * cols] * rows
                            #text = [[[empty for c in range(cols)] * rows]]
                            text = list()
                            for i in range(0, rows):
                                text.append(list())
                                for j in range(0, cols):
                                    text[i].append(empty)
                            cur_x = cur_y = 0

                        elif m := match(b'[012]?K', csi): # clear in line
                            if m.end() == 1 or csi[0] == b'0':
                                pass
                            elif csi[0] == b'1':
                                pass
                            elif csi[0] == b'2':
                                pass

                        elif m := match(b'[0-9;]*m', csi): # SGR
                            #print("SGR")
                            sgr = csi[:-1].split(b';')

                            if sgr[0] == b'1': # bold
                                bold = True

                            elif sgr[0] == b'3': # italic/oblique
                                oblique = True

                            elif sgr[0] == b'4': # underline
                                underline = True

                            elif sgr[0] == b'30': # fg black
                                fg = BLACK

                            elif sgr[0] == b'31': # fg red
                                fg = RED

                            elif sgr[0] == b'32': # fg green
                                fg = GREEN

                            elif sgr[0] == b'33': # fg yellow
                                fg = YELLOW

                            elif sgr[0] == b'34': # fg blue
                                fg = BLUE

                            elif sgr[0] == b'35': # fg magenta
                                fg = MAGENTA

                            elif sgr[0] == b'36': # fg cyan
                                fg = CYAN

                            elif sgr[0] == b'37': # fg white
                                fg = WHITE

                            elif sgr[0] == b'38': # set fg color
                                if sgr[1] == b'5': # 8-bit color
                                    pass # how to convert 8-bit to Xlib/24-bit?
                                elif sgr[1] == b'2': # 24-bit/true color
                                    fg = int(sgr[2])*256*256 + int(sgr[1])*256 + int(sgr[0])

                            elif sgr[0] == b'39': # default fg color
                                fg = DEFAULT_FG

                            elif sgr[0] == b'40': # bg black
                                bg = BLACK

                            elif sgr[0] == b'41': # bg red
                                bg = RED

                            elif sgr[0] == b'42': # bg green
                                bg = GREEN

                            elif sgr[0] == b'43': # bg yellow
                                bg = YELLOW

                            elif sgr[0] == b'44': # bg blue
                                bg = BLUE

                            elif sgr[0] == b'45': # bg magenta
                                bg = MAGENTA

                            elif sgr[0] == b'46': # bg cyan
                                bg = CYAN

                            elif sgr[0] == b'47': # bg white
                                bg = WHITE

                            elif sgr[0] == b'48': # set bg color
                                if sgr[1] == b'5': # 8-bit color
                                    pass # how to convert 8-bit to Xlib/24-bit?
                                elif sgr[1] == b'2': # 24-bit/true color
                                    print("setting bg")
                                    bg = int(sgr[2])*256*256 + int(sgr[1])*256 + int(sgr[0])

                            elif sgr[0] == b'39': # default bg color
                                bg = DEFAULT_BG

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
                            text[cur_y][cur_x] = (c, blink, underline, bold, oblique, fg, bg)

                        except IndexError:
                            print("cur_y, cur_x:", cur_y, cur_x)
                            print("len(text):", len(text))
                            print("len(text[cur_y]):", len(text[cur_y]))
                            exit()

                        cur_x += 1

                        #print("end read while..")
            # end while

            s += 1
            #print("ms select end", s)
            ready_fds = select([master, x11_fd], [], [], 0)
            #print("end select loop")


        #print("Read...")

        while x11_fd in ready_fds[0]:
            while disp.pending_events():
                #print("Getting event..")

                e = disp.next_event()

                if e.type == X.Expose:
                    #print("expose")
                    redraw()

                elif e.type == X.KeyRelease:
                    #print("key release")
                    # update modifier state
                    if e.detail in modifier_dict['Shift']:
                        mod_state &= ~(1)

                    elif e.detail in modifier_dict['Alt']:
                        #print("release alt")
                        mod_state &= ~(2)

                    elif e.detail in modifier_dict['Control']:
                        pass

                elif e.type == X.KeyPress:
                    #print("key press")

                    # update modifier state
                    if e.detail in modifier_dict['Shift']:
                        #print("shift")
                        mod_state |= 1

                    elif e.detail in modifier_dict['Alt']:
                        #print("alt")
                        mod_state |= 2

                    elif e.detail in modifier_dict['Control']:
                        #print("ctrl")
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

                        if ls:
                            write(master, ls.encode()) 

            s += 1
            #print("x select end", s)
            ready_fds = select([master, x11_fd], [], [], 0)

main()
