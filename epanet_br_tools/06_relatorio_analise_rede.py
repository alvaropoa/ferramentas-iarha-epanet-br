# -*- coding: utf-8 -*-
"""
Ferramenta 6 — Relatório de Análise da Rede (padrão IARHA-ATLAS) + mapas temáticos
Uso (parâmetros no EPANET):
    "<pasta>\\06_relatorio_analise_rede.py" $INPFILE
Opcional: PMIN PMAX VMIN VMAX K1   (padrão 10 40 0.4 3.5 1.2)
    "<pasta>\\06_relatorio_analise_rede.py" $INPFILE 10 40 0.4 3.5 1.2

Simula o projeto com o runepanet.exe do próprio EPANET 2.2 Brasil e abre no navegador
um relatório A4 com: topologia, pressões, hidráulica, demandas, distribuições em km de
rede, balanço do sistema, capacidade de reservação, top 10, diagnóstico automático e
mapas temáticos (pressão, perda de carga, velocidade, demanda, elevação e diâmetro).
Tudo é convertido para SI (m, mm, mca, L/s, m/s, m/km). Não altera o projeto.
"""
import os, sys, math, base64, datetime, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import Inp, SaidaBinaria, arg_arquivo, avisar, simular, resultados_de, esc, numeros
import config_relatorio

AQUI = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ajustes rápidos
# Valores padrão — a ferramenta 7 (janela de configuração) grava os seus em config_relatorio.json
DECIMAL = "."          # separador decimal dos números
P_ALTA = 50.0          # mca — card "P > 50 mca" e alerta de VRP
J_ALTO = 10.0          # m/km — card "Rede J > 10 m/km"

NAVY, BLUE, AMBER = "#00295C", "#034EA2", "#FCAF17"
GREEN, RED, AMBER2, SLATE = "#2E9E62", "#E5532D", "#E39A0F", "#8497B0"
LINHA = "#C9D3DF"

# conversões para SI
CONV_P = {0: 0.7030696, 1: 0.1019716, 2: 1.0, 3: 10.19716, 4: 0.3048}               # -> mca
CONV_Q = {0: 28.316847, 1: 0.0630902, 2: 43.812636, 3: 52.616782, 4: 14.276410,       # -> L/s
          5: 1.0, 6: 1 / 60, 7: 1e6 / 86400, 8: 1 / 3.6, 9: 1 / 86.4, 10: 1000.0}


def aplicar_config(cfg):
    """Copia cores, separador decimal e critérios da configuração para as variáveis do módulo."""
    global DECIMAL, P_ALTA, J_ALTO, NAVY, BLUE, AMBER, GREEN, RED, AMBER2, SLATE
    c = cfg["cores"]
    NAVY, BLUE, AMBER, GREEN = c["primaria"], c["destaque"], c["realce"], c["ok"]
    RED, AMBER2, SLATE = c["critico"], c["alerta"], c["neutra"]
    DECIMAL = cfg["decimal"]
    P_ALTA, J_ALTO = cfg["criterios"]["palta"], cfg["criterios"]["jalto"]


def g(x):
    """Número curto (%g) com o separador decimal escolhido."""
    s = "%g" % x
    return s.replace(".", DECIMAL) if DECIMAL != "." else s


def logo_html(caminho):
    if not caminho:
        return ""
    p = caminho if os.path.isabs(caminho) else os.path.join(AQUI, caminho)
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}.get(os.path.splitext(p)[1].lower())
    if not mime or not os.path.isfile(p):
        return ""
    with open(p, "rb") as f:
        return "<img class='logo' src='data:%s;base64,%s' alt='Logo'>" % (mime, base64.b64encode(f.read()).decode())


def n(x, casas=2):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    s = "%.*f" % (casas, x)
    return s.replace(".", DECIMAL) if DECIMAL != "." else s


def gradiente(c0, c1, k):
    """k cores entre c0 e c1 (hex)."""
    a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    if k == 1:
        return [c1]
    return ["#%02X%02X%02X" % tuple(round(a[j] + (b[j] - a[j]) * t / (k - 1)) for j in range(3)) for t in range(k)]


def classe(v, limites):
    """Índice da classe de v em limites crescentes [l0, l1, ..., ln] (n classes; abertas nas pontas)."""
    for i in range(1, len(limites) - 1):
        if v < limites[i]:
            return i - 1
    return len(limites) - 2


# ---------------------------------------------------------------- fontes embutidas
def fontes_css():
    regras = []
    for fam, arq, peso in (("Bebas Neue", "bebas-neue-latin-400-normal.woff2", 400),
                           ("Fira Sans Condensed", "fira-sans-condensed-latin-400-normal.woff2", 400),
                           ("Fira Sans Condensed", "fira-sans-condensed-latin-600-normal.woff2", 600),
                           ("Fira Sans Condensed", "fira-sans-condensed-latin-700-normal.woff2", 700)):
        p = os.path.join(AQUI, "fontes", arq)
        if os.path.exists(p):
            with open(p, "rb") as f:
                regras.append("@font-face{font-family:'%s';font-weight:%d;font-style:normal;src:url(data:font/woff2;base64,%s) format('woff2')}"
                              % (fam, peso, base64.b64encode(f.read()).decode()))
    return "".join(regras)


CSS_MODELO = """
@page{size:A4;margin:12mm 12mm 14mm}
:root{--navy:%(NAVY)s;--blue:%(BLUE)s;--amber:%(AMBER)s;--green:%(GREEN)s;--red:%(RED)s;--amber2:%(AMBER2)s;
--slate:#5B6B80;--muted:%(SLATE)s;--rule:#E3E8EF;--panel:#F8FAFC;--zebra:#F3F5F9;--tx:#1A2740}
*{box-sizing:border-box}
body{margin:0;background:#fff;color:var(--tx);font:10pt/1.45 'Fira Sans Condensed','Arial Narrow',Arial,sans-serif}
.pagina{max-width:200mm;margin:0 auto;padding:14px 16px 40px}
.cab{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.cab .logo{max-height:58px;max-width:180px;object-fit:contain}
.cab h1{font:700 21pt/1.2 Helvetica,Arial,sans-serif;color:#000;margin:6px 0 2px}.cab .sub{font-size:12pt;color:var(--navy);font-weight:600;margin:0 0 2px}
.cab p{font:11pt Helvetica,Arial,sans-serif;color:#000;margin:0 0 14px}
.faixa{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:8.5pt;color:var(--slate);margin:0 0 14px}
.faixa b{color:var(--navy);font-weight:600}
.titulo{display:inline-block;font-weight:700;font-size:12pt;color:var(--navy);border-bottom:3px solid var(--amber);padding-bottom:2px;margin:4px 0 6px}
.sec{position:relative;font-weight:700;font-size:8.5pt;letter-spacing:.06em;text-transform:uppercase;color:var(--blue);
border-bottom:2px solid var(--rule);padding-bottom:3px;margin:16px 0 9px}
.sec:after{content:"";position:absolute;left:0;bottom:-2px;width:28px;height:2px;background:var(--amber)}
.sec small{font-weight:600;color:var(--muted);letter-spacing:0;text-transform:none;margin-left:6px}
.kpis{display:grid;gap:8px 16px}.k6{grid-template-columns:repeat(6,1fr)}.k4{grid-template-columns:repeat(4,1fr)}
.kpi{position:relative;padding:3px 0 3px 13px;min-height:52px}
.kpi:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;border-radius:4px;background:var(--c,var(--blue))}
.kpi .lb{display:block;font-weight:600;font-size:7.5pt;letter-spacing:.04em;text-transform:uppercase;color:var(--slate)}
.kpi b{display:block;font:400 21pt/1 'Bebas Neue','Arial Narrow',Arial,sans-serif;color:var(--navy);letter-spacing:.01em;margin-top:2px}
.kpi .un{display:block;font-size:7.5pt;color:var(--muted);margin-top:1px}
.graficos{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.graf{background:var(--panel);border:1px solid var(--rule);border-radius:6px;padding:8px 8px 4px}
.graf h4,.fig h4{margin:0 0 2px;font-weight:700;font-size:8pt;letter-spacing:.05em;text-transform:uppercase;color:var(--navy);display:flex;align-items:center;gap:6px}
.graf h4:before,.fig h4:before{content:"";width:4px;height:11px;border-radius:2px;background:var(--amber)}
svg{display:block;width:100%%;height:auto}
.eixo{font:9px 'Fira Sans Condensed',Arial,sans-serif;fill:#8A97A8}.val{font:600 9px 'Fira Sans Condensed',Arial,sans-serif;fill:#3A4A5E}
.grade{stroke:#E6EBF1;stroke-width:1}
.caixa{border:1px solid var(--rule);border-radius:6px;padding:10px 12px}
.caixa .nota{font-size:8.5pt;color:var(--muted);margin:0 0 6px}
.fluxo{display:flex;align-items:stretch;gap:6px}.fluxo .op{align-self:center;color:var(--muted);font-weight:700}
.bx{flex:1;border-radius:6px;padding:7px 6px;text-align:center}
.bx b{display:block;font:400 18pt/1 'Bebas Neue','Arial Narrow',Arial,sans-serif}
.bx span{display:block;font-weight:600;font-size:7.5pt;margin-top:2px}
.bx.azul{background:var(--blue);color:#fff}.bx.ambar{background:var(--amber);color:var(--navy)}
.bx.verde{background:#E3F2E8;border:4px solid #A9D7B9;color:#1F6B3F}.bx.rosa{background:#FCE7E1;border:4px solid #F2B8A6;color:#B23A1E}
.bx.cinza{background:#E9EEF6;border:4px solid #D2DBE7;color:#4A5D78}
.res{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px}
.ok-msg,.er-msg{border-radius:5px;padding:6px 10px;font-weight:600;font-size:9pt}
.ok-msg{background:#DDF6E6;color:#1F7A4D}.er-msg{background:#FCE7E1;color:#B23A1E}
table{width:100%%;border-collapse:separate;border-spacing:0;font-size:8.5pt;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
th{background:var(--blue);color:#fff;font-weight:700;text-align:left;padding:5px 8px}
td{padding:4px 8px;border-top:1px solid var(--rule);font-variant-numeric:tabular-nums}
tr:nth-child(even) td{background:var(--zebra)}td.n{font-weight:700;color:var(--navy)}
.diag{border:1px solid var(--rule);border-left:4px solid var(--blue);border-radius:6px;background:var(--zebra);padding:8px 12px}
.diag p{margin:5px 0;font-size:9pt}
.tg{display:inline-block;font-weight:700;font-size:7.5pt;padding:1px 7px;border-radius:3px;margin-right:6px}
.tg.cr{background:#FBE3DC;color:#C0392B}.tg.at{background:var(--amber);color:var(--navy)}.tg.okk{background:#DFF3E6;color:#1F7A4D}
.fig{border:1px solid var(--rule);border-radius:6px;padding:8px 10px 6px;margin:0 0 10px;break-inside:avoid}
.fig svg{background:#FBFCFE;border-radius:4px}
.leg{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:8pt;color:var(--slate);margin-top:5px}
.leg i{display:inline-block;width:11px;height:11px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.leg em{font-style:normal;color:var(--muted)}
.cap{font-size:8pt;color:var(--muted);margin:3px 0 0}
.acoes{position:sticky;top:0;z-index:2;display:flex;justify-content:flex-end;padding:8px 16px;background:rgba(255,255,255,.92);border-bottom:1px solid var(--rule)}
.acoes button{font:700 9pt 'Fira Sans Condensed',Arial,sans-serif;background:var(--blue);color:#fff;border:0;border-radius:4px;padding:7px 12px;cursor:pointer}
.quebra{break-before:page}
@media print{.acoes{display:none}.pagina{padding:0;max-width:none}.graf,.caixa,.kpis,table tr,.diag p{break-inside:avoid}.sec{break-after:avoid}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:700px){.k6{grid-template-columns:repeat(3,1fr)}.k4{grid-template-columns:repeat(2,1fr)}.graficos{grid-template-columns:1fr}.fluxo{flex-wrap:wrap}}
"""


# ---------------------------------------------------------------- componentes
def sec(t, nota=""):
    return "<div class='sec'>%s%s</div>" % (esc(t), "<small>%s</small>" % esc(nota) if nota else "")


def kpi(rotulo, valor, unidade="", cor=None):
    cor = cor or BLUE
    return ("<div class='kpi' style='--c:%s'><span class='lb'>%s</span><b>%s</b><span class='un'>%s</span></div>"
            % (cor, esc(rotulo), esc(valor), esc(unidade) or "&nbsp;"))


def _passo(vmax):
    for p in (0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 2000, 5000):
        if vmax / p <= 7:
            return p
    return 10000


def histograma(titulo, rotulos, valores, cores, ylabel="km de rede"):
    W, H, ml, mr, mt, mb = 520, 232, 46, 8, 18, 30
    vmax = max(valores + [0.0])
    passo = _passo(vmax if vmax > 0 else 1)
    topo = max(passo, math.ceil(vmax / passo) * passo)
    Y = lambda v: mt + (topo - v) * (H - mt - mb) / topo
    k = len(valores); slot = (W - ml - mr) / k; bw = slot * 0.72
    s = ["<svg viewBox='0 0 %d %d' role='img' aria-label='%s'>" % (W, H, esc(titulo))]
    v = 0.0
    while v <= topo + 1e-9:
        s.append("<line class='grade' x1='%d' x2='%d' y1='%.1f' y2='%.1f'/><text class='eixo' x='%d' y='%.1f' text-anchor='end'>%s</text>"
                 % (ml, W - mr, Y(v), Y(v), ml - 6, Y(v) + 3, ("%g" % v)))
        v += passo
    for i, (r, val, c) in enumerate(zip(rotulos, valores, cores)):
        x = ml + i * slot + (slot - bw) / 2
        h = max(Y(0) - Y(val), 0)
        if val > 0:
            s.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' rx='3' fill='%s'/>" % (x, Y(val), bw, max(h, 1.5), c))
            s.append("<text class='val' x='%.1f' y='%.1f' text-anchor='middle'>%s</text>" % (x + bw / 2, Y(val) - 4, n(val, 2)))
        s.append("<text class='eixo' x='%.1f' y='%d' text-anchor='middle'>%s</text>" % (ml + i * slot + slot / 2, H - 12, esc(r)))
    s.append("<text class='eixo' x='12' y='%d' transform='rotate(-90 12 %d)' text-anchor='middle' style='font-weight:600;fill:#5B6B80'>%s</text>"
             % ((mt + H - mb) // 2, (mt + H - mb) // 2, esc(ylabel)))
    s.append("</svg>")
    return "<div class='graf'><h4>%s</h4>%s</div>" % (esc(titulo), "".join(s))


class Mapa:
    """Geometria da rede (coordenadas + vértices) para desenhar mapas temáticos em SVG."""

    def __init__(self, inp, larg=740):
        self.xy = {}
        for t in inp.tabela("COORDINATES"):
            if len(t) >= 3:
                self.xy[t[0]] = (float(t[1]), float(t[2]))
        self.vert = {}
        for t in inp.tabela("VERTICES"):
            self.vert.setdefault(t[0], []).append((float(t[1]), float(t[2])))
        self.trechos = [(sec, t[0], t[1], t[2]) for sec in ("PIPES", "PUMPS", "VALVES") for t in inp.tabela(sec)]
        self.ok = len(self.xy) >= 2
        if not self.ok:
            return
        xs = [p[0] for p in self.xy.values()]; ys = [p[1] for p in self.xy.values()]
        for pts in self.vert.values():
            xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
        self.x0, self.x1, self.y0, self.y1 = min(xs), max(xs), min(ys), max(ys)
        dx, dy = (self.x1 - self.x0) or 1, (self.y1 - self.y0) or 1
        self.L = larg
        self.H = int(min(max(larg * dy / dx, 280), 430))   # cabe 2 mapas por página A4
        m = 14
        self.e = min((larg - 2 * m) / dx, (self.H - 2 * m) / dy)
        self.ox = (larg - dx * self.e) / 2; self.oy = (self.H - dy * self.e) / 2
        self.dx = dx
        nn = len(self.xy)
        self.r = 4.2 if nn < 300 else (2.4 if nn < 3000 else 1.2)
        self.w = 1.6 if nn < 3000 else 0.9

    def P(self, p):
        return (self.ox + (p[0] - self.x0) * self.e, self.H - self.oy - (p[1] - self.y0) * self.e)

    def desenhar(self, cor_trecho=None, larg_trecho=None, cor_no=None, fontes=(), tanques=(), rotulos=()):
        if not self.ok:
            return "<p class='cap'>O projeto não tem coordenadas — mapa indisponível.</p>"
        s = ["<svg viewBox='0 0 %d %d'>" % (self.L, self.H)]
        camadas = {}
        for sec_, lid, n1, n2 in self.trechos:
            if n1 not in self.xy or n2 not in self.xy:
                continue
            pts = [self.P(self.xy[n1])] + [self.P(v) for v in self.vert.get(lid, [])] + [self.P(self.xy[n2])]
            cor = (cor_trecho or {}).get(lid, LINHA)
            w = (larg_trecho or {}).get(lid, self.w if cor_trecho else self.w * 0.9)
            tr = " stroke-dasharray='4 3'" if sec_ != "PIPES" else ""
            # cores mais "fortes" por cima
            camadas.setdefault(cor == LINHA, []).append(
                "<polyline points='%s' fill='none' stroke='%s' stroke-width='%.1f' stroke-linecap='round' stroke-linejoin='round'%s/>"
                % (" ".join("%.1f,%.1f" % p for p in pts), cor, w, tr))
        s += camadas.get(True, []) + camadas.get(False, [])
        if cor_no is not None:
            for nid, c in cor_no.items():
                if nid in self.xy and nid not in fontes and nid not in tanques:
                    x, y = self.P(self.xy[nid])
                    s.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='%s' stroke='#fff' stroke-width='0.6'/>" % (x, y, self.r, c))
        for nid in list(fontes) + list(tanques):
            if nid in self.xy:
                x, y = self.P(self.xy[nid])
                s.append("<rect x='%.1f' y='%.1f' width='10' height='10' rx='2' fill='%s' stroke='#fff' stroke-width='1.2'/>"
                         % (x - 5, y - 5, NAVY if nid in fontes else AMBER))
                s.append("<text class='val' x='%.1f' y='%.1f' style='paint-order:stroke;stroke:#fff;stroke-width:3px'>%s</text>" % (x + 8, y - 6, esc(nid)))
        for nid in rotulos:
            if nid in self.xy:
                x, y = self.P(self.xy[nid])
                s.append("<text class='val' x='%.1f' y='%.1f' style='paint-order:stroke;stroke:#fff;stroke-width:3px'>%s</text>" % (x + 6, y - 5, esc(nid)))
        # barra de escala (m)
        alvo = self.dx / 5
        passo = 10 ** len(str(int(alvo))) / 10 if alvo >= 1 else 1
        for k in (1, 2, 5, 10):
            if passo * k >= alvo:
                passo *= k; break
        s.append("<rect x='14' y='%d' width='%.1f' height='4' fill='%s'/><text class='eixo' x='14' y='%d'>%s m</text>"
                 % (self.H - 14, passo * self.e, NAVY, self.H - 19, ("%g" % passo)))
        # norte
        s.append("<g transform='translate(%d,22)'><path d='M0,-12 L6,6 L0,2 L-6,6 Z' fill='%s'/><text class='eixo' x='0' y='17' text-anchor='middle'>N</text></g>"
                 % (self.L - 20, NAVY))
        s.append("</svg>")
        return "".join(s)


def figura(num, titulo, svg, legenda, nota):
    leg = "".join("<span><i style='background:%s'></i>%s <em>%s</em></span>" % (c, esc(r), esc(q)) for c, r, q in legenda)
    return ("<div class='fig'><h4>Figura %d — %s</h4>%s<div class='leg'>%s</div><p class='cap'>%s</p></div>"
            % (num, esc(titulo), svg, leg, esc(nota)))


# ---------------------------------------------------------------- relatório
def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    cfg = config_relatorio.carregar()
    if cfg["perguntar"] and not os.environ.get("IARHA_SEM_JANELA"):
        cfg = config_relatorio.janela(cfg, botao_gerar=True)
        if cfg is None:
            return None          # cancelado
    aplicar_config(cfg)
    cr = cfg["criterios"]

    def eh_numero(s):
        try:
            float(s.strip("`'\" ").replace(",", ".")); return True
        except ValueError:
            return False
    tem_out = len(sys.argv) > 2 and not eh_numero(sys.argv[2])
    out = SaidaBinaria(resultados_de(arg_arquivo(2, "arquivo de resultados")) if tem_out else simular(inp.caminho))
    # números depois de $INPFILE no cadastro têm prioridade sobre a configuração
    pmin_l, pmax_l, vmin_l, vmax_l, K1 = numeros(sys.argv[(3 if tem_out else 2):], [cr["pmin"], cr["pmax"], cr["vmin"], cr["vmax"], cr["k1"]])

    spec = importlib.util.spec_from_file_location("verif", os.path.join(AQUI, "02_verificar_consistencia.py"))
    verif = importlib.util.module_from_spec(spec); spec.loader.exec_module(verif)
    achados = verif.verificar(inp)

    # ---- unidades -> SI
    si = out.u_vazao >= 5
    fL = 1.0 if si else 0.3048            # comprimento/cota -> m
    fD = 1.0 if si else 25.4              # diâmetro -> mm
    fV = 1.0 if si else 0.3048            # velocidade -> m/s
    fQ = CONV_Q.get(out.u_vazao, 1.0)     # vazão -> L/s
    fP = CONV_P.get(out.u_pressao, 1.0)   # pressão -> mca

    nos, links = out.nos, out.links
    J = [i for i in range(out.nn) if i not in out.idx_fontes]
    Jset = set(J)
    RNF = [i for i in out.idx_fontes if i not in out.idx_tanques]
    RNV = sorted(out.idx_tanques)
    T = [j for j in range(out.nl) if out.link_tipo[j] <= 1]          # tubos
    ini = [x - 1 for x in out.link_ini]; fim = [x - 1 for x in out.link_fim]
    comp = [c * fL for c in out.comprimentos]
    diam = [d * fD for d in out.diametros]
    cota = [c * fL for c in out.cotas]
    ext_km = sum(comp[j] for j in T) / 1000

    # ---- série temporal: consumo, instantes, envelopes
    consumo = []; pmin_env = {i: (1e9, 0) for i in J}; pmax_env = {i: (-1e9, 0) for i in J}
    for k in range(out.nperiodos):
        r = out.completo(k)
        consumo.append(sum(r["dem"][i] for i in J) * fQ)
        for i in J:
            p = r["pres"][i] * fP
            if p < pmin_env[i][0]: pmin_env[i] = (p, k)
            if p > pmax_env[i][0]: pmax_env[i] = (p, k)
    kmax = max(range(out.nperiodos), key=lambda k: consumo[k])
    kmin = min(range(out.nperiodos), key=lambda k: consumo[k])
    R = out.completo(kmax)
    pres = [p * fP for p in R["pres"]]
    dem = [d * fQ for d in R["dem"]]
    vaz = [q * fQ for q in R["vaz"]]
    vel = [abs(v) * fV for v in R["vel"]]
    perda = [abs(h) for h in R["perda"]]                               # m/km (ou ft/kft = m/km)
    aberto = [s > 2 for s in R["sta"]]
    Ta = [j for j in T if aberto[j]]
    Rmin = out.completo(kmin)
    pres_min_cons = [p * fP for p in Rmin["pres"]]
    dem_min_cons = [d * fQ for d in Rmin["dem"]]

    def media_trecho(valores, j):
        """Média do valor nos nós finais do trecho que são de consumo (ignora reservatórios)."""
        vs = [valores[x] for x in (ini[j], fim[j]) if x in Jset]
        return sum(vs) / len(vs) if vs else None

    # ---- indicadores
    pJ = [pres[i] for i in J]
    p_media = sum(pJ) / len(pJ) if pJ else 0
    p_min_env = min(pmin_env[i][0] for i in J); i_pmin = min(J, key=lambda i: pmin_env[i][0])
    p_max_env = max(pmax_env[i][0] for i in J); i_pmax = max(J, key=lambda i: pmax_env[i][0])
    n_baixa = [i for i in J if pres[i] < pmin_l]
    n_alta = [i for i in J if pmax_env[i][0] > P_ALTA]
    pmax_por_no = [pmax_env[i][0] if i in Jset else 0 for i in range(out.nn)]
    km_p40 = sum(comp[j] for j in T if (media_trecho(pmax_por_no, j) or 0) > pmax_l) / 1000
    j_medio = (sum(perda[j] * comp[j] for j in Ta) / sum(comp[j] for j in Ta)) if Ta else 0
    km_j10 = sum(comp[j] for j in Ta if perda[j] > J_ALTO) / 1000
    km_vmax = sum(comp[j] for j in Ta if vel[j] > vmax_l) / 1000
    km_vmin = sum(comp[j] for j in Ta if vel[j] < vmin_l) / 1000
    cJ = [cota[i] for i in J]
    elev_media = sum(cJ) / len(cJ) if cJ else 0
    n_vrp = sum(1 for t in out.link_tipo if t == 3)
    n_bombas = sum(1 for t in out.link_tipo if t == 2)
    n_valv = sum(1 for t in out.link_tipo if t >= 3)
    nos_dem = [i for i in J if dem[i] > 1e-9]
    q_medio = sum(consumo) / len(consumo)
    base_total = 0.0
    dmap = {t[0]: float(t[2]) for t in inp.tabela("JUNCTIONS") if len(t) > 2}
    if inp.tabela("DEMANDS"):
        ac = {}
        for t in inp.tabela("DEMANDS"):
            ac[t[0]] = ac.get(t[0], 0.0) + float(t[1])
        dmap.update(ac)
    base_total = sum(dmap.values()) * fQ

    # ---- balanço no instante de maior consumo (convenção do .out: demanda < 0 = fornecimento)
    ent_rnf = -sum(dem[i] for i in RNF)
    ent_rnv = -sum(dem[i] for i in RNV)
    cons_pico = sum(dem[i] for i in J)

    # ---- reservação (tanques do INP)
    vol_disp = 0.0; n_tq_vol = 0
    for t in inp.tabela("TANKS"):
        try:
            nmin, nmax, D = float(t[3]), float(t[4]), float(t[5])
        except (IndexError, ValueError):
            continue
        vol_disp += math.pi / 4 * (D * fL) ** 2 * max(nmax - nmin, 0) * fL; n_tq_vol += 1
    q_dm = q_medio * K1
    v_dist = q_dm * 86.4                       # m³/dia
    nec13, nec15 = v_dist / 3, v_dist / 5

    titulo = " ".join(inp.tabela("TITLE")[0]) if inp.tabela("TITLE") else os.path.splitext(os.path.basename(inp.caminho))[0]
    agora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    estatica = out.nperiodos < 2
    h = []
    _aberta = {"k": None, "i": 0}

    def _secao(chave):
        """Fecha a seção anterior (removendo-a se estiver desligada) e abre a próxima."""
        if _aberta["k"] and not cfg["secoes"].get(_aberta["k"], True):
            del h[_aberta["i"]:]
        _aberta["k"], _aberta["i"] = chave, len(h)

    # ================================================================ CABEÇALHO
    h.append("<div class='acoes'><button onclick='print()'>Imprimir / salvar PDF</button></div><div class='pagina'>")
    extra = "".join("<p class='sub'>%s</p>" % esc(x) for x in (cfg["subtitulo"],) if x)
    resp = (" · Responsável técnico: %s" % esc(cfg["responsavel"])) if cfg["responsavel"] else ""
    h.append("<div class='cab'><div><h1>%s</h1>%s<p>Gerado em %s%s</p></div>%s</div>"
             % (esc(cfg["titulo"]), extra, agora, resp, logo_html(cfg["logo"])))
    h.append("<div class='titulo'>Relatório — %d nós · %d trechos · Rede completa</div>" % (out.nn, out.nl))
    h.append("<div class='faixa'><span>Projeto <b>%s</b></span><span>Período <b>%s h · %d passos</b></span>"
             "<span>Maior consumo <b>%s</b></span><span>Menor consumo <b>%s</b></span><span>Fórmula <b>%s</b></span></div>"
             % (esc(titulo), n(out.duracao / 3600, 0), out.nperiodos, out.hora(kmax), out.hora(kmin), esc(inp.formula())))

    # ================================================================ TOPOLOGIA
    _secao("topologia")
    h.append(sec("Topologia da rede"))
    h.append("<div class='kpis k6'>" + kpi("Trechos", str(out.nl)) + kpi("Nós", str(out.nn)) + kpi("Extensão", n(ext_km, 2), "km")
             + kpi("Tanques/Reserv.", str(len(RNV) + len(RNF)), "%d RNV · %d RNF" % (len(RNV), len(RNF)))
             + kpi("VRP", str(n_vrp), "", AMBER) + kpi("Bombas", str(n_bombas), "", GREEN) + "</div>")

    # ================================================================ PRESSÃO
    _secao("pressao")
    h.append(sec("Pressão — nós (mca)", "média no instante de maior consumo (%s) · mín./máx. no período" % out.hora(kmax)))
    h.append("<div class='kpis k6'>" + kpi("Média", n(p_media, 1), "mca", GREEN) + kpi("Mínima", n(p_min_env, 1), "mca", RED)
             + kpi("Máxima", n(p_max_env, 1), "mca", AMBER) + kpi("P < %g mca" % pmin_l, str(len(n_baixa)), "nós", RED)
             + kpi("P > %g mca" % P_ALTA, str(len(n_alta)), "nós", AMBER) + kpi("Rede P > %g mca" % pmax_l, n(km_p40, 2), "km", AMBER) + "</div>")

    # ================================================================ HIDRÁULICA
    _secao("hidraulica")
    h.append(sec("Hidráulica — trechos", "instante de maior consumo (%s)" % out.hora(kmax)))
    h.append("<div class='kpis k6'>" + kpi("J médio", n(j_medio, 2), "m/km", AMBER) + kpi("Rede J > %g m/km" % J_ALTO, n(km_j10, 2), "km", RED)
             + kpi("Rede V > %g m/s" % vmax_l, n(km_vmax, 2), "km", RED) + kpi("Rede V < %g m/s" % vmin_l, n(km_vmin, 2), "km", SLATE)
             + kpi("Elevação média", n(elev_media, 1), "m") + kpi("Elev. mín / máx", "%s / %s" % (n(min(cJ), 0), n(max(cJ), 0)), "m") + "</div>")

    # ================================================================ DEMANDAS
    _secao("demandas")
    h.append(sec("Demandas cadastradas"))
    h.append("<div class='kpis k4'>" + kpi("Nós com demanda", str(len(nos_dem)), "de %d nós de consumo" % len(J))
             + kpi("Demanda base", n(base_total, 3), "L/s", GREEN) + kpi("Consumo no pico (%s)" % out.hora(kmax), n(cons_pico, 2), "L/s", RED)
             + kpi("Consumo médio", n(q_medio, 2), "L/s") + "</div>")

    # ================================================================ DISTRIBUIÇÕES
    _secao("distribuicoes")
    h.append(sec("Distribuições", "km de rede por classe · instante de maior consumo (%s)" % out.hora(kmax)))
    lim_p = [0, 5, 10, 20, 30, 40, 50, 60, 100, 200]
    rot_p = ["0–5", "5–10", "10–20", "20–30", "30–40", "40–50", "50–60", "60–100", "100–200"]
    cor_p = [RED, RED, GREEN, GREEN, BLUE, AMBER, AMBER2, AMBER2, AMBER2]
    km_p = [0.0] * 9
    for j in T:
        pm = media_trecho(pres, j)
        if pm is not None:
            km_p[classe(max(pm, 0), lim_p)] += comp[j] / 1000
    lim_j = [0, 3, 6, 9, 10, 15, 20, 50, 100]
    rot_j = ["0–3", "3–6", "6–9", "9–10", "10–15", "15–20", "20–50", "50–100"]
    cor_j = [GREEN, GREEN, GREEN, GREEN, RED, RED, RED, RED]
    km_j = [0.0] * 8
    for j in Ta:
        km_j[classe(perda[j], lim_j)] += comp[j] / 1000
    e0, e1 = min(cJ), max(cJ)
    pe = next((p for p in (5, 10, 20, 25, 50, 100) if (math.ceil(e1 / p) - math.floor(e0 / p)) <= 8), 200)
    lim_e = [math.floor(e0 / pe) * pe + pe * i for i in range(int(math.ceil(e1 / pe) - math.floor(e0 / pe)) + 1)]
    if len(lim_e) < 2:
        lim_e = [lim_e[0], lim_e[0] + pe]
    rot_e = ["%g–%g" % (lim_e[i], lim_e[i + 1]) for i in range(len(lim_e) - 1)]
    cor_e = gradiente(*cfg["mapas"]["elevacao"]["rampa"], len(rot_e))
    km_e = [0.0] * len(rot_e)
    cota_no = list(cota)
    for j in T:
        em = media_trecho(cota_no, j)
        if em is not None:
            km_e[classe(em, lim_e)] += comp[j] / 1000
    lim_d = [0, 50, 100, 150, 200, 250, 300, 400, 600, 1000]
    rot_d = ["0–50", "50–100", "100–150", "150–200", "200–250", "250–300", "300–400", "400–600", "600–1000"]
    cor_d = gradiente(*cfg["mapas"]["diametro"]["rampa"], 9)
    km_d = [0.0] * 9
    for j in T:
        km_d[classe(diam[j], lim_d)] += comp[j] / 1000
    h.append("<div class='graficos'>" + histograma("Pressões nos nós", rot_p, km_p, cor_p) + histograma("Perda de carga nos trechos (m/km)", rot_j, km_j, cor_j)
             + histograma("Elevação dos nós (m)", rot_e, km_e, cor_e) + histograma("Diâmetros da rede (mm)", rot_d, km_d, cor_d) + "</div>")

    # ================================================================ BALANÇO
    _secao("balanco")
    h.append(sec("Balanço do sistema", "instante de maior consumo (%s)" % out.hora(kmax)))
    tq_txt = "Tanques (L/s)" if ent_rnv >= 0 else "Tanques enchendo (L/s)"
    h.append("<div class='caixa'><p class='nota'>Reservatórios de nível fixo + tanques → consumo nos nós (resultados do motor EPANET)</p>"
             "<div class='fluxo'><div class='bx azul'><b>%s</b><span>Reservatórios RNF (L/s)</span></div><div class='op'>+</div>"
             "<div class='bx ambar'><b>%s</b><span>%s</span></div><div class='op'>→</div>"
             "<div class='bx verde'><b>%s</b><span>Consumo (L/s)</span></div></div>"
             "<p class='nota' style='margin:6px 0 0'>Fechamento do balanço: %s L/s (diferença entre entrada e consumo).</p></div>"
             % (n(ent_rnf, 2), n(abs(ent_rnv), 2), tq_txt, n(cons_pico, 2), n(ent_rnf + ent_rnv - cons_pico, 3)))

    # ================================================================ RESERVAÇÃO
    _secao("reservacao")
    h.append(sec("Capacidade de reservação", "K1 = %s · NBR 12217 (1/3 do volume do dia de maior consumo)" % n(K1, 2)))
    h.append("<div class='caixa'><p class='nota'>Q médio (período simulado) → Q do dia de maior consumo (×K1) → Volume distribuído no dia máximo</p>"
             "<div class='fluxo'><div class='bx azul'><b>%s</b><span>Q médio (L/s)</span></div><div class='op'>×K1 →</div>"
             "<div class='bx azul'><b>%s</b><span>Q dia máx (L/s)</span></div><div class='op'>→</div>"
             "<div class='bx ambar'><b>%s</b><span>V distribuído (m³/dia)</span></div></div>"
             % (n(q_medio, 2), n(q_dm, 2), n(v_dist, 1)))
    h.append("<div class='fluxo' style='margin-top:6px'><div class='bx rosa'><b>%s</b><span>Necessário 1/3 (m³)</span></div>"
             "<div class='bx rosa'><b>%s</b><span>Necessário 1/5 (m³)</span></div>"
             "<div class='bx verde'><b>%s</b><span>Disponível (tanques, m³)</span></div></div>" % (n(nec13, 1), n(nec15, 1), n(vol_disp, 1)))
    if n_tq_vol:
        msgs = []
        for frac, nec in (("1/3", nec13), ("1/5", nec15)):
            sobra = vol_disp - nec
            if sobra >= 0:
                msgs.append("<div class='ok-msg'>✓ %s: suficiente · superávit %s m³ (%s%%)</div>" % (frac, n(sobra, 1), n(100 * sobra / nec if nec else 0, 0)))
            else:
                msgs.append("<div class='er-msg'>✕ %s: insuficiente · déficit %s m³ (%s%%)</div>" % (frac, n(-sobra, 1), n(-100 * sobra / nec if nec else 0, 0)))
        h.append("<div class='res'>%s</div>" % "".join(msgs))
    h.append("<p class='nota' style='margin:6px 0 0'>%d tanque(s) (RNV) com volume útil calculado por π·D²/4·(nível máx − nível mín); "
             "reservatórios de nível fixo (RNF) não entram na reservação.%s</p></div>"
             % (n_tq_vol, "" if estatica else " Q médio = média das %d etapas simuladas." % out.nperiodos))

    # ================================================================ TOP 10
    _secao("top10")
    def tabela(cab, linhas, negrito):
        s = "<table><tr>" + "".join("<th>%s</th>" % esc(c) for c in cab) + "</tr>"
        for ln in linhas:
            s += "<tr>" + "".join("<td%s>%s</td>" % (" class='n'" if i in negrito else "", c) for i, c in enumerate(ln)) + "</tr>"
        return s + "</table>"
    topJ = sorted(Ta, key=lambda j: -perda[j])[:10]
    h.append(sec("Top 10 — maior perda de carga unitária", "instante de maior consumo (%s)" % out.hora(kmax)))
    h.append(tabela(["Trecho", "Comp. (m)", "Ø (mm)", "Q (L/s)", "v (m/s)", "J (m/km)"],
                    [[esc(links[j]), n(comp[j], 0), n(diam[j], 0), n(vaz[j], 2), n(vel[j], 2), n(perda[j], 2)] for j in topJ], {5}))
    topPmin = sorted(J, key=lambda i: pres[i])[:10]
    h.append(sec("Top 10 — menor pressão", "instante de maior consumo (%s)" % out.hora(kmax)))
    st = lambda p: "Baixa" if p < pmin_l else ("Alta" if p > pmax_l else "Normal")
    h.append(tabela(["Nó", "Elevação (m)", "Demanda (L/s)", "Pressão (mca)", "Status"],
                    [[esc(nos[i]), n(cota[i], 1), n(dem[i], 3), n(pres[i], 2), st(pres[i])] for i in topPmin], {3}))
    topPmax = sorted(J, key=lambda i: -pres_min_cons[i])[:10]
    h.append(sec("Top 10 — maior pressão", "instante de menor consumo (%s)" % out.hora(kmin)))
    h.append(tabela(["Nó", "Elevação (m)", "Demanda (L/s)", "Pressão (mca)", "Status"],
                    [[esc(nos[i]), n(cota[i], 1), n(dem_min_cons[i], 3), n(pres_min_cons[i], 2), st(pres_min_cons[i])] for i in topPmax], {3}))

    # ================================================================ DIAGNÓSTICO
    _secao("diagnostico")
    nJ = max(len(J), 1)
    d = []
    if n_baixa:
        d.append(("cr", "%d nós (%s%% da rede) com pressão abaixo de %g mca no instante de maior consumo — risco de contaminação e falha no abastecimento. "
                  "Pior caso: %s com %s mca às %s. Reforço de rede ou setorização recomendados."
                  % (len(n_baixa), n(100 * len(n_baixa) / nJ, 1), pmin_l, nos[i_pmin], n(p_min_env, 1), out.hora(pmin_env[i_pmin][1]))))
    if n_alta:
        d.append(("at", "%d nós (%s%% da rede) com pressão acima de %g mca no período (máx. %s mca em %s às %s) — avaliar instalação de VRP para proteção da rede e redução de perdas físicas."
                  % (len(n_alta), n(100 * len(n_alta) / nJ, 1), P_ALTA, n(p_max_env, 1), nos[i_pmax], out.hora(pmax_env[i_pmax][1]))))
    if km_j10 > 0:
        d.append(("at", "%s km (%s%% da extensão da rede) com J > %g m/km — possível subdimensionamento ou obstrução. Priorizar inspeção e substituição de trechos críticos."
                  % (n(km_j10, 2), n(100 * km_j10 / ext_km if ext_km else 0, 1), J_ALTO)))
    if km_p40 > 0:
        d.append(("at", "%s km (%s%% da extensão da rede) submetidos a pressão acima de %g mca — risco elevado de rupturas. Verificar estado das tubulações."
                  % (n(km_p40, 2), n(100 * km_p40 / ext_km if ext_km else 0, 1), pmax_l)))
    if km_vmax > 0:
        d.append(("cr", "%s km com velocidade acima de %g m/s no pico — risco de transientes e desgaste." % (n(km_vmax, 2), vmax_l)))
    if km_vmin > 0:
        d.append(("at", "%s km (%s%% da extensão) com velocidade abaixo de %g m/s no pico — possível estagnação e perda de qualidade da água."
                  % (n(km_vmin, 2), n(100 * km_vmin / ext_km if ext_km else 0, 1), vmin_l)))
    if n_tq_vol and vol_disp < nec13:
        d.append(("cr", "Reservação insuficiente: disponível %s m³ para %s m³ necessários (1/3 do dia de maior consumo, K1 = %s)."
                  % (n(vol_disp, 1), n(nec13, 1), n(K1, 2))))
    ne = sum(1 for a in achados if a[0] == "erro")
    if ne:
        d.append(("cr", "%d inconsistência(s) graves no cadastro do modelo (ex.: %s — %s)." % (ne, achados[0][1], achados[0][3])))
    elif achados:
        d.append(("at", "%d aviso(s) de cadastro (ex.: %s em %s)." % (len(achados), achados[0][1], achados[0][2])))
    d.append(("okk", "Rede completa analisada: %d nós · %d trechos · %s km · pressão média %s mca no pico."
              % (out.nn, out.nl, n(ext_km, 2), n(p_media, 1))))
    nome_tg = {"cr": "Crítico", "at": "Atenção", "okk": "Ok"}
    h.append(sec("Diagnóstico automático"))
    h.append("<div class='diag'>" + "".join("<p><span class='tg %s'>%s</span>%s</p>" % (c, nome_tg[c], esc(t)) for c, t in d) + "</div>")

    # ================================================================ MAPAS
    _secao("mapas")
    mp = Mapa(inp)
    fontes_id = {nos[i] for i in RNF}; tanques_id = {nos[i] for i in RNV}
    h.append("<div class='quebra'></div>" + sec("Mapas temáticos", "instante de maior consumo (%s)" % out.hora(kmax)))
    fig = 0

    def cont(idx, cls_de, k_cls, peso=None):
        q = [0.0] * k_cls
        for x in idx:
            q[cls_de(x)] += (peso(x) if peso else 1)
        return q

    def classes_cfg(chave, un):
        """Limites e cores de um mapa por classes, vindos da configuração."""
        d = cfg["mapas"][chave]
        lims = [-1e18] + list(d["limites"]) + [1e18]
        rot = ["< %s" % g(d["limites"][0])] + ["%s–%s" % (g(a), g(b)) for a, b in zip(d["limites"], d["limites"][1:])] \
            + ["> %s %s" % (g(d["limites"][-1]), un)]
        return lims, d["cores"], rot

    mapas_on = cfg["mapas"]
    # 1 pressão
    if mapas_on["pressao"]["ativo"]:
        lim_mp, cores_mp, rot_mp = classes_cfg("pressao", "mca")
        k_mp = len(cores_mp)
        cmp_ = lambda i: classe(pres[i], lim_mp)
        q = cont(J, cmp_, k_mp)
        fig += 1
        h.append(figura(fig, "Pressão nos nós (mca)",
                        mp.desenhar(cor_no={nos[i]: cores_mp[cmp_(i)] for i in J}, fontes=fontes_id, tanques=tanques_id,
                                    rotulos=[nos[i] for i in sorted(J, key=lambda i: pres[i])[:5]]),
                        [(cores_mp[c], rot_mp[c], "%d nós" % q[c]) for c in range(k_mp)],
                        "Rótulos: os 5 nós de menor pressão. Quadrados: reservatórios e tanques."))
    # 2 perda de carga
    if mapas_on["perda"]["ativo"]:
        lim_mj, cores_mj, rot_mj = classes_cfg("perda", "m/km")
        k_mj = len(cores_mj)
        cj = lambda j: classe(perda[j], lim_mj)
        q = cont(Ta, cj, k_mj, lambda j: comp[j] / 1000)
        fig += 1
        h.append(figura(fig, "Perda de carga unitária nos trechos (m/km)",
                        mp.desenhar(cor_trecho={links[j]: cores_mj[cj(j)] for j in Ta},
                                    larg_trecho={links[j]: mp.w * (1.8 if perda[j] >= J_ALTO else 1.1) for j in Ta},
                                    fontes=fontes_id, tanques=tanques_id),
                        [(cores_mj[c], rot_mj[c], "%s km" % n(q[c], 2)) for c in range(k_mj)], "Trechos fechados em cinza claro."))
    # 3 velocidade
    if mapas_on["velocidade"]["ativo"]:
        lim_mv, cores_mv, rot_mv = classes_cfg("velocidade", "m/s")
        k_mv = len(cores_mv)
        cv = lambda j: classe(vel[j], lim_mv)
        q = cont(Ta, cv, k_mv, lambda j: comp[j] / 1000)
        fig += 1
        h.append(figura(fig, "Velocidade nos trechos (m/s)",
                        mp.desenhar(cor_trecho={links[j]: cores_mv[cv(j)] for j in Ta},
                                    larg_trecho={links[j]: mp.w * (1.8 if cv(j) >= k_mv - 2 else 1.1) for j in Ta},
                                    fontes=fontes_id, tanques=tanques_id),
                        [(cores_mv[c], rot_mv[c], "%s km" % n(q[c], 2)) for c in range(k_mv)], "Velocidade em módulo no instante de maior consumo."))
    # 4 demanda (quartis das demandas positivas)
    if mapas_on["demanda"]["ativo"]:
        pos = sorted(dem[i] for i in nos_dem)
        if pos:
            qs = [pos[min(len(pos) - 1, int(len(pos) * f))] for f in (0.25, 0.5, 0.75)]
            lim_md = [1e-9, qs[0], qs[1], qs[2], 1e18]
            cores_md = gradiente(*mapas_on["demanda"]["rampa"], 4)
            cdm = lambda i: -1 if dem[i] <= 1e-9 else classe(dem[i], lim_md)
            cor_dm = {nos[i]: ("#D5DCE6" if cdm(i) < 0 else cores_md[cdm(i)]) for i in J}
            qd = [sum(1 for i in nos_dem if cdm(i) == c) for c in range(4)]
            rot_md = ["até %s" % n(qs[0], 3), "%s–%s" % (n(qs[0], 3), n(qs[1], 3)), "%s–%s" % (n(qs[1], 3), n(qs[2], 3)), "> %s L/s" % n(qs[2], 3)]
            leg = [("#D5DCE6", "sem demanda", "%d nós" % (len(J) - len(nos_dem)))] + [(cores_md[c], rot_md[c], "%d nós" % qd[c]) for c in range(4)]
        else:
            cor_dm = {nos[i]: "#D5DCE6" for i in J}; leg = [("#D5DCE6", "sem demanda", "%d nós" % len(J))]
        fig += 1
        h.append(figura(fig, "Demanda nos nós (L/s)", mp.desenhar(cor_no=cor_dm, fontes=fontes_id, tanques=tanques_id), leg,
                        "Classes por quartis das demandas no instante de maior consumo."))
    # 5 elevação
    ce = lambda i: classe(cota[i], lim_e)
    q = cont(J, ce, len(rot_e))
    if mapas_on["elevacao"]["ativo"]:
        fig += 1
        h.append(figura(fig, "Elevação dos nós (m)", mp.desenhar(cor_no={nos[i]: cor_e[ce(i)] for i in J}, fontes=fontes_id, tanques=tanques_id),
                      [(cor_e[c], rot_e[c] + " m", "%d nós" % q[c]) for c in range(len(rot_e))], "Cota do terreno informada no modelo."))
    # 6 diâmetro
    usados = [c for c in range(9) if km_d[c] > 0]
    cdd = lambda j: classe(diam[j], lim_d)
    larg_d = {links[j]: 0.8 + 2.6 * (usados.index(cdd(j)) + 1) / max(len(usados), 1) for j in T}
    if mapas_on["diametro"]["ativo"]:
        fig += 1
        h.append(figura(fig, "Diâmetros da rede (mm)",
                      mp.desenhar(cor_trecho={links[j]: cor_d[cdd(j)] for j in T}, larg_trecho=larg_d, fontes=fontes_id, tanques=tanques_id),
                      [(cor_d[c], rot_d[c] + " mm", "%s km" % n(km_d[c], 2)) for c in usados], "Espessura proporcional à classe de diâmetro."))

    _secao(None)
    h.append("<p class='cap' style='margin-top:14px'>Simulação hidráulica executada pelo motor do EPANET 2.2 Brasil (USEPA · LENHS/UFPB). "
             "Resultados refletem o modelo e os dados de entrada; calibração e validação de campo são responsabilidade do projetista.</p></div>")

    caminho = os.path.join(__import__("tempfile").gettempdir(), "IARHA_Analise_Rede.html")
    doc = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
           "<title>%s</title><style>%s%s</style></head><body>%s</body></html>"
           % (esc("Análise da Rede — " + titulo), fontes_css(),
              CSS_MODELO % dict(NAVY=NAVY, BLUE=BLUE, AMBER=AMBER, GREEN=GREEN, RED=RED, AMBER2=AMBER2, SLATE=SLATE), "".join(h)))
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    __import__("webbrowser").open("file:///" + caminho.replace("\\", "/"))
    return caminho


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        avisar("Análise da Rede — erro", "%s\n\n%s" % (e, traceback.format_exc()[-700:]), erro=True)
