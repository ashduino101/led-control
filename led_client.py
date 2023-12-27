import socket
import time

import colour

IP = '192.168.0.2'  # your server IP

BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 255)
ORANGE = (255, 50, 0, 255)
YELLOW = (255, 150, 0, 255)
GREEN = (0, 255, 0, 255)
CYAN = (0, 255, 255, 255)
BLUE = (0, 0, 255, 255)
PURPLE = (180, 0, 255, 255)
WHITE = (255, 255, 255, 255)
COLORS = (BLACK, RED, ORANGE, YELLOW, GREEN, CYAN, BLUE, PURPLE, WHITE)


max_brightness = 0.5


def normalize_led(led):
    if led[3] > 255:
        led[3] = 255
    a = led[3] / 255
    r = int(led[0] * max_brightness * a)
    g = int(led[1] * max_brightness * a)
    b = int(led[2] * max_brightness * a)
    return r, g, b


class BaseCommand:
    cmd_id = -1


class ClearCommand(BaseCommand):
    cmd_id = 0

    def __init__(self):
        pass

    def encode(self):
        return b''


class SetRGBCommand(BaseCommand):
    cmd_id = 1

    def __init__(self, idx, color):
        self.idx = idx
        self.color = normalize_led(color)

    def encode(self):
        return bytes([self.idx, *self.color])


class FillCommand(BaseCommand):
    cmd_id = 2

    def __init__(self, color):
        self.color = normalize_led(color)

    def encode(self):
        return bytes([*self.color])


class ShowCommand(BaseCommand):
    cmd_id = 3

    def __init__(self):
        pass

    def encode(self):
        return b''


def encode_packet(cmds):
    data = len(cmds).to_bytes(2, 'little')
    for cmd in cmds:
        data += bytes([cmd.cmd_id]) + cmd.encode()

    return data


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setblocking(True)

sock.connect((IP, 7805))


def send_cmds(cmds):
    sock.send(encode_packet(cmds))

def pixels_clear():
    send_cmds([ClearCommand()])

def pixels_set(i, v):
    send_cmds([SetRGBCommand(i, v)])


def pixels_fill(v):
    send_cmds([FillCommand(v)])


def pixels_show():
    send_cmds([ShowCommand()])


def wheel(pos):
    # Input a value 0 to 255 to get a color value.
    # The colours are a transition r - g - b - back to r.
    if pos < 0 or pos > 255:
        return 0, 0, 0, 255
    if pos < 85:
        return 255 - pos * 3, pos * 3, 0, 255
    if pos < 170:
        pos -= 85
        return 0, 255 - pos * 3, pos * 3, 255
    pos -= 170
    return pos * 3, 0, 255 - pos * 3, 255


NUM_LEDS = 93 + 96  # desk + chair


def interpolate_colors(col1, col2, num):
    red_difference = col2[0] - col1[0]
    green_difference = col2[1] - col1[1]
    blue_difference = col2[2] - col1[2]
    alpha_difference = col2[3] - col1[3]

    red_delta = red_difference / num
    green_delta = green_difference / num
    blue_delta = blue_difference / num
    alpha_delta = alpha_difference / num

    colors = []
    for i in range(0, num):
        colors.append((round(col1[0] + (red_delta * i)),
                       round(col1[1] + (green_delta * i)),
                       round(col1[2] + (blue_delta * i)),
                       round(col1[3] + (alpha_delta * i))))

    return colors


def rainbow(offset=0):
    for i in range(NUM_LEDS):
        rc_index = (i * 256 // NUM_LEDS) + offset
        pixels_set(i, wheel(rc_index & 255))
    pixels_show()


def rainbow_cycle(wait):
    for j in range(255):
        rainbow(j)
        time.sleep(wait)


def pattern(colors, width, cmd=SetRGBCommand, show=False):
    cmds = []
    i = 0
    for j in range(NUM_LEDS // (width * len(colors)) + 1):
        for c in colors:
            for k in range(width):
                if len(cmds) >= NUM_LEDS:
                    break
                cmds.append(cmd(i, c))
                i += 1
    if show:
        cmds.append(ShowCommand())
    send_cmds(cmds)


def pattern_chase(colors, width, cmd=SetRGBCommand):
    offset = 0
    while True:
        _c = colors[-offset:] + colors[:-offset]
        pattern(_c, width, cmd, show=True)
        offset += 1
        if offset >= len(colors):
            offset = 0
        time.sleep(0.5)


def gradient2(col1, col2):
    colors = interpolate_colors(col1, col2, NUM_LEDS)
    cmds = []
    for i, c in enumerate(colors):
        cmds.append(SetRGBCommand(i, c))
    send_cmds(cmds)


def gradientn(*cols):
    leds_per_gradient = NUM_LEDS // (len(cols) - 1)
    cmds = []
    for i, col in enumerate(cols[:-1]):
        grad = interpolate_colors(col, cols[i + 1], leds_per_gradient)
        for j, c in enumerate(grad):
            led = (i * leds_per_gradient) + j
            cmds.append(SetRGBCommand(led, c))
    send_cmds(cmds)


def gradient_fade(start1, end1, start2, end2, num, delay):
    start = interpolate_colors(start1, end1, num)
    end = interpolate_colors(start2, end2, num)
    for i in range(num):
        gradient2(start[i], end[i])
        pixels_show()
        time.sleep(delay)


pixels_fill([0, 0, 0, 0])

# pattern([[0x3a, 0x62, 0xce, 0xff], [0x88, 0x0e, 0x73, 0xff], [0xf8, 0xff, 0xf9, 0xff], [0x88, 0x0e, 0x73, 0xff]], 3)
# pattern([RED, ORANGE, YELLOW, GREEN, BLUE, PURPLE], 5)
# pattern_chase([(8, 16, 212, 255), (255, 125, 0, 255), WHITE], 3)
# pixels_fill(CYAN)
# rainbow()
# pixels_fill([0xf8, 0x2e, 0x73, 0xff])
# while True:
#     rainbow_cycle(0.05)
# for i in range(NUM_LEDS):
#     if i > 0:
#         pixels_set(i - 1, [0, 255, 255, 255])
#     pixels_set(i, [255, 0, 0, 255])
#     time.sleep(0.1)
#     print(i)
#     pixels_show()
# gradientn(CYAN, PURPLE)
# gradient_fade(RED, GREEN, ORANGE, BLUE, 100, 0.01)
# pixels_fill([255, 0, 0, 255])
pixels_show()
