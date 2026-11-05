"""Shared dark theme for the ADM dashboard. Colours, fonts and small widget helpers only.

Plain Tkinter (ttk + the 'clam' theme) cannot draw gradients, true rounded corners or glow,
so cards are drawn on a Canvas with smoothed outlines to get close to the dashboard look.
No application logic lives here.
"""
from __future__ import annotations

# Dark navy palette with an indigo/cyan accent, styled after the product mockup.
PAGE = '#0A0F1E'          # window background (deepest)
SIDEBAR = '#0D1424'       # left navigation
PANEL = '#111A2E'         # card / panel background
PANEL_HI = '#16203A'      # raised element
BORDER = '#233150'        # hairline borders
INK = '#E7ECF6'           # primary text
MUTED = '#8A95AC'         # secondary text
FAINT = '#5C6881'         # tertiary text

BRAND = '#7C3AED'         # purple primary
BRAND2 = '#4F46E5'        # indigo
BRAND_HI = '#8B5CF6'
CYAN = '#22D3EE'          # live / running accent
ON_BRAND = '#FFFFFF'
SUCCESS = '#22C55E'
SUCCESS_BG = '#14321F'
WARN = '#F59E0B'
DANGER = '#F87171'
DANGER_BG = '#3A1B1E'

FAMILY = 'Segoe UI'


def font(size: int = 10, weight: str = 'normal') -> tuple:
    return (FAMILY, size) if weight == 'normal' else (FAMILY, size, weight)


def apply(root) -> object:
    from tkinter import ttk
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    root.configure(bg=PAGE)
    style.configure('.', background=PAGE, foreground=INK, font=font(10),
                    fieldbackground=PANEL, bordercolor=BORDER, focuscolor=PAGE)

    style.configure('TFrame', background=PAGE)
    style.configure('Panel.TFrame', background=PANEL)
    style.configure('Sidebar.TFrame', background=SIDEBAR)
    style.configure('Header.TFrame', background=PAGE)

    style.configure('TLabel', background=PAGE, foreground=INK, font=font(10))
    style.configure('Muted.TLabel', background=PAGE, foreground=MUTED, font=font(9))
    style.configure('Title.TLabel', background=PAGE, foreground=INK, font=font(20, 'bold'))
    style.configure('Sub.TLabel', background=PAGE, foreground=MUTED, font=font(10))
    style.configure('Section.TLabel', background=PAGE, foreground=FAINT, font=font(9, 'bold'))
    style.configure('Panel.TLabel', background=PANEL, foreground=INK, font=font(10))
    style.configure('PanelTitle.TLabel', background=PANEL, foreground=INK, font=font(11, 'bold'))
    style.configure('PanelMuted.TLabel', background=PANEL, foreground=MUTED, font=font(9))
    style.configure('Sidebar.TLabel', background=SIDEBAR, foreground=MUTED, font=font(10))
    style.configure('Brand.TLabel', background=SIDEBAR, foreground=INK, font=font(13, 'bold'))

    for name, bg, fg, bg_act, pad, fnt in (
            ('Primary.TButton', BRAND, ON_BRAND, BRAND_HI, (18, 10), font(10, 'bold')),
            ('Accent.TButton', BRAND2, ON_BRAND, '#6366F1', (18, 10), font(10, 'bold')),
            ('Secondary.TButton', PANEL_HI, INK, '#1E2A47', (15, 9), font(10)),
            ('Danger.TButton', DANGER_BG, DANGER, '#4A2327', (15, 9), font(10))):
        style.configure(name, background=bg, foreground=fg, font=fnt, relief='flat',
                        borderwidth=0, padding=pad, anchor='center')
        style.map(name, background=[('pressed', bg_act), ('active', bg_act), ('disabled', '#182036')],
                  foreground=[('disabled', FAINT)], relief=[('pressed', 'flat'), ('active', 'flat')])

    style.configure('TEntry', fieldbackground=PANEL_HI, foreground=INK, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, borderwidth=1, padding=7, insertcolor=INK)
    style.map('TEntry', bordercolor=[('focus', BRAND)], lightcolor=[('focus', BRAND)])

    style.configure('TRadiobutton', background=PAGE, foreground=INK, font=font(10))
    style.map('TRadiobutton', background=[('active', PAGE)],
              indicatorcolor=[('selected', BRAND), ('!selected', PANEL_HI)])

    style.configure('TNotebook', background=PAGE, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure('TNotebook.Tab', background=PAGE, foreground=MUTED, padding=(14, 8),
                    font=font(10), borderwidth=0)
    style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', INK)])

    style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=INK,
                    rowheight=30, borderwidth=0, font=font(10))
    style.configure('Treeview.Heading', background=PANEL_HI, foreground=MUTED, relief='flat',
                    font=font(9, 'bold'), padding=(10, 7), borderwidth=0)
    style.map('Treeview', background=[('selected', '#1E2A47')], foreground=[('selected', INK)])
    style.map('Treeview.Heading', background=[('active', '#1E2A47')])

    style.configure('Vertical.TScrollbar', background=PANEL_HI, troughcolor=PAGE,
                    bordercolor=PAGE, arrowcolor=MUTED, borderwidth=0)
    return style


def header(parent, title: str, subtitle: str):
    """A simple dark title block (used by the standalone request window)."""
    from tkinter import ttk
    band = ttk.Frame(parent, style='TFrame')
    ttk.Label(band, text=title, style='Title.TLabel').pack(anchor='w', padx=24, pady=(16, 0))
    ttk.Label(band, text=subtitle, style='Sub.TLabel').pack(anchor='w', padx=24, pady=(2, 14))
    return band


def round_rect(canvas, x1, y1, x2, y2, r=12, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def card(parent, height=None):
    """A flat rounded panel drawn on a Canvas; returns (holder, content_frame)."""
    import tkinter as tk
    holder = tk.Frame(parent, bg=PAGE, highlightthickness=0, bd=0)
    canvas = tk.Canvas(holder, bg=PAGE, highlightthickness=0, bd=0,
                       height=height or 1)
    canvas.pack(fill='both', expand=True)
    inner = tk.Frame(canvas, bg=PANEL)
    win = canvas.create_window(14, 14, anchor='nw', window=inner, tags='content')

    def paint(event=None):
        canvas.delete('bg')
        w, h = canvas.winfo_width(), canvas.winfo_height()
        round_rect(canvas, 1, 1, w - 2, h - 2, 14, fill=PANEL, outline=BORDER, width=1, tags='bg')
        canvas.tag_lower('bg')
        canvas.itemconfig(win, width=w - 28, height=h - 28)
    canvas.bind('<Configure>', paint)
    return holder, inner


def stat_tile(parent, icon, label, accent=CYAN):
    """A compact KPI tile drawn on a Canvas. Returns (widget, set_value)."""
    import tkinter as tk
    holder = tk.Frame(parent, bg=PAGE)
    canvas = tk.Canvas(holder, bg=PAGE, highlightthickness=0, bd=0, height=86)
    canvas.pack(fill='both', expand=True)
    state = {'value': '—'}

    def paint(event=None):
        canvas.delete('all')
        w, h = canvas.winfo_width(), canvas.winfo_height()
        round_rect(canvas, 1, 1, w - 2, h - 2, 14, fill=PANEL, outline=BORDER, width=1)
        round_rect(canvas, 14, 24, 52, 62, 10, fill=PANEL_HI, outline='')
        canvas.create_text(33, 43, text=icon, fill=accent, font=font(15))
        canvas.create_text(66, 32, text=label, fill=MUTED, font=font(9), anchor='w')
        state['value_id'] = canvas.create_text(66, 54, text=state['value'], fill=INK,
                                                font=font(16, 'bold'), anchor='w')
    canvas.bind('<Configure>', paint)

    def set_value(v):
        state['value'] = str(v)
        if 'value_id' in state:
            try:
                canvas.itemconfig(state['value_id'], text=state['value'])
            except Exception:
                pass
    return holder, set_value


def document(parent, **kw):
    import tkinter as tk
    frame = tk.Frame(parent, bg=BORDER, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BORDER)
    text = tk.Text(frame, wrap='word', state='disabled', relief='flat', bd=0,
                   bg=PANEL, fg=INK, font=font(10), padx=16, pady=14,
                   insertbackground=INK, selectbackground='#1E2A47', **kw)
    text.pack(fill='both', expand=True)
    return frame, text


def entry_text(parent, **kw):
    import tkinter as tk
    frame = tk.Frame(parent, bg=BORDER, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BRAND)
    text = tk.Text(frame, wrap='word', relief='flat', bd=0, bg=PANEL_HI, fg=INK,
                   font=font(11), padx=12, pady=10, insertbackground=INK,
                   selectbackground='#1E2A47', **kw)
    text.pack(fill='both', expand=True)
    return frame, text
