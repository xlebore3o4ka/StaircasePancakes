import pygame
import re

def parse_html(text):
    tokens = re.split(r'(<[^>]+>)', text)
    state = {'b': False, 'i': False, 'c': None}
    for t in tokens:
        if t.startswith("<") and t.endswith(">"):
            tl = t.lower()
            if tl == "<b>": state['b'] = True
            elif tl == "</b>": state['b'] = False
            elif tl == "<i>": state['i'] = True
            elif tl == "</i>": state['i'] = False
            elif tl.startswith("<color="):
                h = t.split("=")[1].strip(">").strip("'").strip('"')
                if h.startswith("#"): h = h[1:]
                if len(h) == 6:
                    state['c'] = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            elif tl == "</color>":
                state['c'] = None
            elif tl == "<br>":
                yield chr(10), state.copy()
        else:
            yield t, state.copy()

def draw_html(surface, text, x, y, width, size, color):
    base_font = pygame.font.SysFont("consolas", size)
    bold_font = pygame.font.SysFont("consolas", size, bold=True)
    italic_font = pygame.font.SysFont("consolas", size, italic=True)
    bi_font = pygame.font.SysFont("consolas", size, bold=True, italic=True)

    words = []
    current_word = ""
    last_state = {'b': False, 'i': False, 'c': None}
    for chunk, state in parse_html(text):
        parts = re.split(r'(\s+)', chunk)
        for p in parts:
            if p.isspace():
                if current_word:
                    words.append((current_word, last_state))
                    current_word = ""
                words.append((p, state))
            elif p == "\n":
                if current_word:
                    words.append((current_word, last_state))
                    current_word = ""
                words.append((chr(10), state))
            else:
                current_word += p
                last_state = state
    if current_word:
        words.append((current_word, last_state))

    cx, cy = x, y
    line_h = size + 6
    for word, state in words:
        if word == chr(10):
            cx = x
            cy += line_h
            continue
        f = base_font
        if state['b'] and state['i']: f = bi_font
        elif state['b']: f = bold_font
        elif state['i']: f = italic_font
        c = state['c'] if state['c'] else color
        w = f.size(word)[0]
        if word.isspace():
            cx += w
            continue
        if cx + w > x + width:
            cx = x
            cy += line_h
        surf = f.render(word, True, c)
        surface.blit(surf, (cx, cy))
        cx += w
