"""Shared visual theme for the ADM windows. Colours, fonts and small widget helpers only.

No application logic lives here. The look is a flat, modern panel: an indigo header band,
a slate page, white inputs, one accent colour for the primary action. Buttons are built with
ttk + the 'clam' theme so their disabled state greys out correctly.
"""
from __future__ import annotations

# Palette (slate + indigo), chosen for contrast in light rooms.
INK = '#0F172A'          # primary text
MUTED = '#64748B'        # secondary text
PAGE = '#EEF1F6'         # window background
SURFACE = '#FFFFFF'      # inputs / panels
BORDER = '#D8DEE9'
BRAND = '#4F46E5'        # indigo primary action
BRAND_DARK = '#4338CA'
BRAND_SOFT = '#EEF2FF'
ON_BRAND = '#FFFFFF'
SUBTLE_BRAND = '#C7D2FE'
GREY = '#E2E8F0'
GREY_DARK = '#CBD5E1'
SUCCESS = '#15803D'
DANGER = '#B91C1C'
PANEL = '#F8FAFC'
DISABLED_BRAND = '#C7D2FE'
DISABLED_TEXT = '#94A3B8'

FAMILY = 'Segoe UI'


def font(size: int = 10, weight: str = 'normal') -> tuple:
    return (FAMILY, size) if weight == 'normal' else (FAMILY, size, weight)


def apply(root) -> object:
    """Install the ttk styles on `root` and paint its background. Returns the Style."""
    from tkinter import ttk
    style = ttk.Style(root)
    try:
        style.theme_use('clam')
    except Exception:
        pass
    root.configure(bg=PAGE)
    style.configure('.', background=PAGE, foreground=INK, font=font(10))

    style.configure('TFrame', background=PAGE)
    style.configure('Card.TFrame', background=SURFACE)
    style.configure('Header.TFrame', background=BRAND)

    style.configure('TLabel', background=PAGE, foreground=INK, font=font(10))
    style.configure('Muted.TLabel', background=PAGE, foreground=MUTED, font=font(9))
    style.configure('Heading.TLabel', background=PAGE, foreground=INK, font=font(12, 'bold'))
    style.configure('Section.TLabel', background=PAGE, foreground=MUTED, font=font(9, 'bold'))
    style.configure('HeaderTitle.TLabel', background=BRAND, foreground=ON_BRAND, font=font(19, 'bold'))
    style.configure('HeaderSub.TLabel', background=BRAND, foreground=SUBTLE_BRAND, font=font(10))
    style.configure('Card.TLabel', background=SURFACE, foreground=INK, font=font(10))
    style.configure('CardMuted.TLabel', background=SURFACE, foreground=MUTED, font=font(9))

    for name, bg, fg, bg_act, pad, fnt in (
            ('Primary.TButton', BRAND, ON_BRAND, BRAND_DARK, (20, 11), font(10, 'bold')),
            ('Secondary.TButton', GREY, INK, GREY_DARK, (16, 9), font(10)),
            ('Danger.TButton', '#FEE2E2', DANGER, '#FECACA', (16, 9), font(10))):
        style.configure(name, background=bg, foreground=fg, font=fnt, relief='flat',
                        borderwidth=0, padding=pad, anchor='center')
        style.map(name,
                  background=[('pressed', bg_act), ('active', bg_act), ('disabled', '#EFF2F7')],
                  foreground=[('disabled', DISABLED_TEXT)],
                  relief=[('pressed', 'flat'), ('active', 'flat')])
    style.map('Primary.TButton', background=[('pressed', BRAND_DARK), ('active', BRAND_DARK),
                                             ('disabled', DISABLED_BRAND)],
              foreground=[('disabled', BRAND_SOFT)])

    style.configure('TEntry', fieldbackground=SURFACE, foreground=INK, bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER, borderwidth=1, padding=7)
    style.map('TEntry', bordercolor=[('focus', BRAND)], lightcolor=[('focus', BRAND)])

    style.configure('TRadiobutton', background=PAGE, foreground=INK, font=font(10))
    style.map('TRadiobutton', background=[('active', PAGE)], indicatorcolor=[('selected', BRAND)])

    style.configure('Treeview', background=SURFACE, fieldbackground=SURFACE, foreground=INK,
                    rowheight=28, borderwidth=0, font=font(10))
    style.configure('Treeview.Heading', background=PANEL, foreground=MUTED, relief='flat',
                    font=font(9, 'bold'), padding=(10, 7), borderwidth=0)
    style.map('Treeview', background=[('selected', BRAND_SOFT)], foreground=[('selected', INK)])
    style.map('Treeview.Heading', background=[('active', GREY)])
    return style


def header(parent, title: str, subtitle: str):
    """A full-width indigo title band."""
    from tkinter import ttk
    band = ttk.Frame(parent, style='Header.TFrame')
    inner = ttk.Frame(band, style='Header.TFrame')
    inner.pack(fill='x', padx=24, pady=(16, 16))
    ttk.Label(inner, text=title, style='HeaderTitle.TLabel').pack(anchor='w')
    ttk.Label(inner, text=subtitle, style='HeaderSub.TLabel').pack(anchor='w', pady=(2, 0))
    return band


def document(parent, **kw):
    """A read-only text panel that looks like a sheet of paper, not a terminal."""
    import tkinter as tk
    frame = tk.Frame(parent, bg=BORDER, bd=0, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BORDER)
    text = tk.Text(frame, wrap='word', state='disabled', relief='flat', bd=0,
                   bg=SURFACE, fg=INK, font=font(10), padx=16, pady=14,
                   insertbackground=INK, selectbackground=BRAND_SOFT, **kw)
    text.pack(fill='both', expand=True)
    return frame, text


def entry_text(parent, **kw):
    """A multi-line input that matches the document panel."""
    import tkinter as tk
    frame = tk.Frame(parent, bg=BORDER, bd=0, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=BRAND)
    text = tk.Text(frame, wrap='word', relief='flat', bd=0, bg=SURFACE, fg=INK,
                   font=font(11), padx=12, pady=10, insertbackground=INK,
                   selectbackground=BRAND_SOFT, **kw)
    text.pack(fill='both', expand=True)
    return frame, text
