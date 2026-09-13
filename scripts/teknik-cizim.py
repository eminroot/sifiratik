# -*- coding: utf-8 -*-
"""Technical drawing: boxes, arrows, as little text as the diagram can carry."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.backends.backend_pdf import PdfPages

plt.rcParams["font.family"] = "DejaVu Sans"

INK, MUTE, RULE, BG = "#0d0d0e", "#5a5a62", "#c9c9c3", "#ffffff"
ACCENT = "#14603d"
A4 = (8.27, 11.69)

def page(fig_size=A4):
    fig = plt.figure(figsize=fig_size)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig_size[0]); ax.set_ylim(0, fig_size[1])
    ax.axis("off"); ax.set_facecolor(BG)
    return fig, ax

def box(ax, x, y, w, h, code, title, lines, accent=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0,rounding_size=0.07",
        linewidth=1.5 if accent else 1.1,
        edgecolor=ACCENT if accent else INK, facecolor="none"))
    if code:
        ax.text(x + 0.16, y + h - 0.26, code, fontsize=8.5, color=ACCENT if accent else MUTE,
                weight="bold", va="center", family="DejaVu Sans")
    ax.text(x + (0.62 if code else 0.16), y + h - 0.26, title, fontsize=10.5, color=INK,
            weight="bold", va="center")
    for i, line in enumerate(lines):
        ax.text(x + 0.16, y + h - 0.55 - i * 0.20, line, fontsize=8.2, color=MUTE, va="center")

def arrow(ax, x, y0, y1, label=""):
    ax.add_patch(FancyArrowPatch((x, y0), (x, y1), arrowstyle="-|>", mutation_scale=15,
                                 linewidth=1.3, color=INK, shrinkA=0, shrinkB=0))
    if label:
        ax.text(x + 0.14, (y0 + y1) / 2, label, fontsize=7.6, color=MUTE, va="center", style="italic")

pdf = PdfPages("docs/TEKNIK-CIZIM.pdf")

# ----------------------------------------------------------------- page 1 --
fig, ax = page()
W, X = 7.0, 0.64
ax.text(X, 11.05, "GÜS-DEDEKTİV", fontsize=17, weight="bold", color=INK)
ax.text(X, 10.78, "Teknik çizim · veri ve karar akışı", fontsize=9.5, color=MUTE)
ax.plot([X, X + W], [10.62, 10.62], color=RULE, linewidth=1)

layers = [
    ("K0", "VERİ KAYNAKLARI", ["GİB GEKAP · TÜİK · GTİP · Sıfır Atık", "saha denetim kayıtları"], "toplu yükleme"),
    ("K1", "ALIM ve DOĞRULAMA", ["şema · VKN → token · birim normalizasyonu", "veri kalite puanı"], "sürümlenmiş panel"),
    ("K2", "ÖZELLİK ÜRETİMİ", ["gecikmeli beyan · emsal (t−1) · ürün ağacı", "ileriye bakış yasağı"], "özellik matrisi"),
    ("K3", "BEKLENTİ MODELİ", ["LightGBM quantile · tarihsel + emsal başlık", "Mondrian CQR kalibrasyonu"], "beklenen aralık  q05–q95"),
    ("K4", "SEKİZ SİNYAL · BİRLEŞTİRME", ["E1 … E8 · izotonik kalibrasyon", "çalıştırılamayan sinyal paydadan düşer"], "0–100 öncelik puanı"),
    ("K5", "AÇIKLAMA ve KARAR KAYDI", ["TreeSHAP · şablonlu gerekçe", "SHA-256 hash-chain"], "REST / JSON"),
    ("K6", "API ve DENETÇİ ARAYÜZÜ", ["FastAPI · React · kuyruk · dosya", "denetçi kararı · denetim izi"], None),
]

y, BH, GAP = 9.45, 0.92, 0.36
for code, title, lines, label in layers:
    box(ax, X, y, W, BH, code, title, lines, accent=(code == "K4"))
    if label:
        arrow(ax, X + W / 2, y - 0.03, y - GAP + 0.03, label)
    y -= BH + GAP

# Two constraints the drawing should carry, as margin notes rather than prose.
ax.add_patch(Rectangle((X, 0.86), W, 0.62, linewidth=1, edgecolor=RULE, facecolor="none"))
ax.text(X + 0.16, 1.28, "Veri kurum içinde kalır. Sistem veri toplamaz.", fontsize=8.2, color=INK, weight="bold")
ax.text(X + 0.16, 1.06, "Nihai karar denetçiye aittir; puan bir önceliktir, ihlal tespiti değildir.",
        fontsize=8.2, color=MUTE)
ax.text(X, 0.55, "Takım KinetiX · TEKNOFEST 2026 Sıfır Atık ve Döngüsel Ekonomi", fontsize=7.5, color=MUTE)
pdf.savefig(fig); fig.savefig("assets/teknik-cizim-1.png", dpi=170)
plt.close(fig)

# ----------------------------------------------------------------- page 2 --
fig, ax = page()
ax.text(X, 11.05, "GÜS-DEDEKTİV", fontsize=17, weight="bold", color=INK)
ax.text(X, 10.78, "Teknik çizim · dağıtım mimarisi", fontsize=9.5, color=MUTE)
ax.plot([X, X + W], [10.62, 10.62], color=RULE, linewidth=1)

box(ax, X + 1.6, 9.45, 3.8, 0.75, "", "DENETÇİ  ·  tarayıcı", ["HTTPS"])
arrow(ax, X + 3.5, 9.42, 8.70, "443 · TLS")

box(ax, X + 1.6, 7.95, 3.8, 0.75, "", "CADDY", ["Let's Encrypt · HSTS · http → https"])
arrow(ax, X + 3.5, 7.92, 7.20, "127.0.0.1:8000")

# The host boundary, drawn so the loopback hop is visibly inside it.
ax.add_patch(Rectangle((X + 0.25, 2.60), W - 0.5, 4.55, linewidth=1.1,
                       edgecolor=INK, facecolor="none", linestyle=(0, (5, 3))))
ax.text(X + 0.42, 6.95, "SUNUCU  ·  Ubuntu 24.04  ·  UFW 22/80/443  ·  fail2ban",
        fontsize=8.2, color=INK, weight="bold")

box(ax, X + 1.0, 5.35, 5.0, 1.05, "", "DOCKER  ·  FastAPI + uvicorn",
    ["derlenmiş React arayüzü aynı kökenden", "oturum çerezi · imzalı"], accent=True)

arrow(ax, X + 2.3, 5.32, 4.45)
arrow(ax, X + 4.7, 5.32, 4.45)
box(ax, X + 0.85, 3.55, 2.4, 0.88, "", "SQLite", ["kalıcı birim", "hash-chain"])
box(ax, X + 3.75, 3.55, 2.4, 0.88, "", "LightGBM", ["quantile · CQR", "imaja gömülü"])

# The one outbound path. Dashed and leaving the server boundary, because it is
# optional, off by default, and the only thing that crosses that line.
ax.add_patch(FancyArrowPatch((X + 6.0, 5.88), (X + 6.95, 5.88), arrowstyle="-|>",
                             mutation_scale=13, linewidth=1.2, color=MUTE, linestyle=(0, (3, 2))))
# Above the arrow, not beside its head: at the head it sat on the dashed
# server boundary the arrow is meant to be seen crossing.
ax.text(X + 6.48, 6.05, "Gemini", fontsize=8.2, color=MUTE, ha="center", weight="bold")
ax.text(X + 0.25, 2.15, "İsteğe bağlı asistan · varsayılan KAPALI · VKN içermeyen brifing",
        fontsize=7.8, color=MUTE, style="italic")

ax.add_patch(Rectangle((X, 0.86), W, 0.62, linewidth=1, edgecolor=RULE, facecolor="none"))
ax.text(X + 0.16, 1.28, "Tek köken: arayüz ve API aynı adresten. CORS yok.", fontsize=8.2, color=INK, weight="bold")
ax.text(X + 0.16, 1.06, "Kapsayıcı yalnızca geri döngüye bağlıdır; dışarıdan tek yol Caddy'dir.",
        fontsize=8.2, color=MUTE)
ax.text(X, 0.55, "eminbaxishli.online", fontsize=7.5, color=MUTE)
pdf.savefig(fig); fig.savefig("assets/teknik-cizim-2.png", dpi=170)
plt.close(fig)
pdf.close()
print("written")
