# -*- coding: utf-8 -*-
"""
Ferramenta 5 — Relatório de Diagnóstico Hidráulico IARHA
Uso (parâmetros no EPANET):
    "<pasta>\\05_relatorio_iarha.py" $INPFILE
Opcional, limites PMIN PMAX VMIN VMAX (padrão 10 40 0.4 3.5):
    "<pasta>\\05_relatorio_iarha.py" $INPFILE 10 40 0.4 3.5

Simula o projeto com o runepanet.exe do próprio EPANET 2.2 Brasil (o menu não
oferece $OUTFILE). Gera um relatório HTML formatado em A4 (capa, síntese,
mapa de pressões, gráficos, consistência e anexo) e abre no navegador.
Para PDF: Ctrl+P > Salvar como PDF (margens "Padrão", com "Gráficos de fundo").

Logo: se existir "logo_iarha.png" (ou .svg) nesta pasta, ele é usado na capa;
senão é desenhado o sol IARHA em SVG.
Não altera o projeto.
"""
import os, sys, base64, importlib.util, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epanet_comum import (Inp, SaidaBinaria, arg_arquivo, gravar_relatorio, fmt, esc, avisar, UNID_VAZAO,
                          simular, resultados_de, numeros)

AQUI = os.path.dirname(os.path.abspath(__file__))
NAVY, AMBER, BLUE, SLATE = "#00295C", "#FCAF17", "#034EA2", "#8497B0"
RED, GREEN = "#C0392B", "#2E8B57"
CONV_P = {0: 0.7030696, 1: 0.1019716, 2: 1.0, 3: 10.19716, 4: 0.3048}


# ------------------------------------------------------------ identidade -----

def logo_html(tam=120):
    for nome, mime in (("logo_iarha.svg", "image/svg+xml"), ("logo_iarha.png", "image/png")):
        p = os.path.join(AQUI, nome)
        if os.path.exists(p):
            with open(p, "rb") as f:
                return "<img src='data:%s;base64,%s' width='%d' alt='IARHA'>" % (
                    mime, base64.b64encode(f.read()).decode(), tam)
    import math
    raios = []
    for i in range(8):
        a = math.radians(i * 45 - 90)
        b1, b2, t = a - math.radians(10), a + math.radians(10), a
        pts = [(50 + 21 * math.cos(b1), 50 + 21 * math.sin(b1)),
               (50 + 34 * math.cos(t), 50 + 34 * math.sin(t)),
               (50 + 21 * math.cos(b2), 50 + 21 * math.sin(b2))]
        raios.append("<polygon points='%s'/>" % " ".join("%.2f,%.2f" % p for p in pts))
    return ("<svg width='%d' height='%d' viewBox='0 0 100 100' role='img' aria-label='IARHA'>"
            "<rect x='5.5' y='5.5' width='89' height='89' rx='14' fill='%s'/>"
            "<g fill='%s'>%s<circle cx='50' cy='50' r='16'/></g></svg>") % (tam, tam, NAVY, AMBER, "".join(raios))


# ---------------------------------------------------------------- gráficos -----

def svg_linhas(series, rotulos_x, ylabel, faixas=(), larg=760, alt=300):
    """series: [(nome, cor, [valores])]; faixas: [(y0, y1, cor, opacidade)]"""
    m = dict(l=52, r=16, t=14, b=38)
    todos = [v for _, _, vs in series for v in vs] + [y for f in faixas for y in f[:2]]
    y0, y1 = min(todos), max(todos)
    pad = (y1 - y0) * 0.08 or 1
    y0, y1 = max(0, y0 - pad) if y0 >= 0 else y0 - pad, y1 + pad
    n = max(len(rotulos_x), 2)
    X = lambda i: m["l"] + i * (larg - m["l"] - m["r"]) / (n - 1)
    Y = lambda v: m["t"] + (y1 - v) * (alt - m["t"] - m["b"]) / (y1 - y0)
    s = ["<svg viewBox='0 0 %d %d' class='graf'>" % (larg, alt)]
    for a, b, cor, op in faixas:
        a, b = max(a, y0), min(b, y1)
        if b > a:
            s.append("<rect x='%d' y='%.1f' width='%d' height='%.1f' fill='%s' opacity='%s'/>"
                     % (m["l"], Y(b), larg - m["l"] - m["r"], Y(a) - Y(b), cor, op))
    passo = _passo(y1 - y0)
    v = (int(y0 / passo) + 1) * passo
    while v < y1:
        s.append("<line x1='%d' x2='%d' y1='%.1f' y2='%.1f' class='grade'/>"
                 "<text x='%d' y='%.1f' class='eixo' text-anchor='end'>%s</text>"
                 % (m["l"], larg - m["r"], Y(v), Y(v), m["l"] - 6, Y(v) + 4, fmt(v, 0)))
        v += passo
    cada = max(1, n // 12)
    for i, r in enumerate(rotulos_x):
        if i % cada == 0:
            s.append("<text x='%.1f' y='%d' class='eixo' text-anchor='middle'>%s</text>" % (X(i), alt - 18, r))
    s.append("<text x='14' y='%d' class='eixo' transform='rotate(-90 14 %d)' text-anchor='middle'>%s</text>"
             % (alt // 2, alt // 2, esc(ylabel)))
    for nome, cor, vs in series:
        pts = " ".join("%.1f,%.1f" % (X(i), Y(v)) for i, v in enumerate(vs))
        s.append("<polyline points='%s' fill='none' stroke='%s' stroke-width='2.2' stroke-linejoin='round'/>" % (pts, cor))
    s.append("</svg>")
    leg = "".join("<span><i style='background:%s'></i>%s</span>" % (c, esc(nm)) for nm, c, _ in series)
    return "<div class='bloco'>" + "".join(s) + "<div class='leg'>%s</div></div>" % leg


def svg_barras(rotulos, valores, cores, ylabel, larg=760, alt=240):
    m = dict(l=52, r=16, t=14, b=40)
    vmax = max(valores + [1])
    n = len(valores)
    w = (larg - m["l"] - m["r"]) / n
    Y = lambda v: m["t"] + (vmax - v) * (alt - m["t"] - m["b"]) / vmax
    s = ["<svg viewBox='0 0 %d %d' class='graf'>" % (larg, alt)]
    passo = _passo(vmax)
    v = passo
    while v <= vmax:
        s.append("<line x1='%d' x2='%d' y1='%.1f' y2='%.1f' class='grade'/>"
                 "<text x='%d' y='%.1f' class='eixo' text-anchor='end'>%s</text>"
                 % (m["l"], larg - m["r"], Y(v), Y(v), m["l"] - 6, Y(v) + 4, fmt(v, 0)))
        v += passo
    for i, (r, v, c) in enumerate(zip(rotulos, valores, cores)):
        x = m["l"] + i * w
        s.append("<rect x='%.1f' y='%.1f' width='%.1f' height='%.1f' fill='%s' rx='2'/>"
                 % (x + 3, Y(v), w - 6, Y(0) - Y(v), c))
        if v:
            s.append("<text x='%.1f' y='%.1f' class='val' text-anchor='middle'>%d</text>" % (x + w / 2, Y(v) - 5, v))
        s.append("<text x='%.1f' y='%d' class='eixo' text-anchor='middle'>%s</text>" % (x + w / 2, alt - 20, r))
    s.append("<text x='14' y='%d' class='eixo' transform='rotate(-90 14 %d)' text-anchor='middle'>%s</text>"
             % (alt // 2, alt // 2, esc(ylabel)))
    return "".join(s) + "</svg>"


def _passo(faixa):
    for p in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 2000, 5000):
        if faixa / p <= 7:
            return p
    return 10000


def svg_mapa(inp, cor_no, cor_link, destaque, fontes, tanques, larg=760):
    xy = {t[0]: (float(t[1]), float(t[2])) for t in inp.tabela("COORDINATES") if len(t) >= 3}
    if len(xy) < 2:
        return "<p class='nota'>O projeto não tem coordenadas — mapa indisponível.</p>"
    vert = {}
    for t in inp.tabela("VERTICES"):
        vert.setdefault(t[0], []).append((float(t[1]), float(t[2])))
    xs, ys = [p[0] for p in xy.values()], [p[1] for p in xy.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    dx, dy = (x1 - x0) or 1, (y1 - y0) or 1
    alt = int(min(max(larg * dy / dx, 260), 620))
    m = 26
    esc_ = min((larg - 2 * m) / dx, (alt - 2 * m) / dy)
    ox = (larg - dx * esc_) / 2
    oy = (alt - dy * esc_) / 2
    P = lambda p: (ox + (p[0] - x0) * esc_, alt - oy - (p[1] - y0) * esc_)
    s = ["<svg viewBox='0 0 %d %d' class='mapa'>" % (larg, alt)]
    for sec in ("PIPES", "PUMPS", "VALVES"):
        for t in inp.tabela(sec):
            if t[1] not in xy or t[2] not in xy:
                continue
            pts = [P(xy[t[1]])] + [P(v) for v in vert.get(t[0], [])] + [P(xy[t[2]])]
            cor, w = cor_link.get(t[0], (SLATE, 2))
            dash = " stroke-dasharray='5 3'" if sec != "PIPES" else ""
            s.append("<polyline points='%s' fill='none' stroke='%s' stroke-width='%.1f' stroke-linecap='round'%s/>"
                     % (" ".join("%.1f,%.1f" % p for p in pts), cor, w, dash))
    r = 6.5 if len(xy) < 300 else (3.0 if len(xy) < 3000 else 1.5)
    for n, p in xy.items():
        x, y = P(p)
        if n in fontes or n in tanques:
            c = NAVY if n in fontes else AMBER
            s.append("<rect x='%.1f' y='%.1f' width='13' height='13' rx='2' fill='%s' stroke='#fff' stroke-width='1.5'/>"
                     % (x - 6.5, y - 6.5, c))
            s.append("<text x='%.1f' y='%.1f' class='rot'>%s</text>" % (x + 10, y - 8, esc(n)))
        else:
            s.append("<circle cx='%.1f' cy='%.1f' r='%.1f' fill='%s' stroke='#fff' stroke-width='1'/>"
                     % (x, y, r, cor_no.get(n, SLATE)))
    for n in destaque:
        if n in xy:
            x, y = P(xy[n])
            s.append("<text x='%.1f' y='%.1f' class='rot'>%s</text>" % (x + 7, y - 7, esc(n)))
    # barra de escala
    alvo = dx / 5
    passo = 10 ** len(str(int(alvo))) / 10
    for k in (1, 2, 5, 10):
        if passo * k >= alvo:
            passo *= k; break
    if passo > 0 and inp.unidades_si():
        wpx = passo * esc_
        s.append("<g class='escala'><rect x='%d' y='%d' width='%.1f' height='5' fill='%s'/>"
                 "<text x='%d' y='%d' class='eixo'>%s m</text></g>"
                 % (m, alt - 16, wpx, NAVY, m, alt - 22, fmt(passo, 0)))
    s.append("</svg>")
    return "".join(s)


# ---------------------------------------------------------------- relatório -----

CSS_REL = """
@page{size:A4;margin:16mm 15mm 18mm}
@page{@bottom-right{content:"Página " counter(page);font:9pt Arial;color:#8497B0}}
:root{--navy:%s;--amber:%s;--blue:%s;--slate:%s;--red:%s;--green:%s;--tx:#1A2740;--bg:#EEF1F5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:10.5pt/1.5 Arial,Helvetica,sans-serif}
.folha{max-width:210mm;margin:16px auto;background:#fff;padding:18mm 16mm;box-shadow:0 2px 14px rgba(0,41,92,.12)}
h1{background:var(--navy);color:#fff;font-size:14pt;margin:0 0 14px;padding:8px 12px;border-radius:2px;letter-spacing:.3px}
h1 b{color:var(--amber);margin-right:8px}
h2{font-size:11.5pt;color:var(--navy);border-bottom:2px solid var(--blue);padding-bottom:3px;margin:22px 0 10px}
p{margin:6px 0}.nota{color:#5b6b80;font-size:9pt}
.capa{min-height:270mm;display:flex;flex-direction:column;padding:0;overflow:hidden}
.capa .topo{background:var(--navy);color:#fff;padding:22mm 16mm 16mm;position:relative}
.capa .topo:after{content:"";position:absolute;left:0;right:0;bottom:-7px;height:7px;background:var(--amber)}
.capa .sup{letter-spacing:3px;font-size:9.5pt;color:var(--amber);margin:22px 0 6px}
.capa .tit{font-size:26pt;line-height:1.15;font-weight:bold;margin:0}
.capa .proj{font-size:14pt;margin-top:10px;opacity:.9}
.capa .meio{padding:14mm 16mm;flex:1}
.capa .rod{padding:8mm 16mm;font-size:9pt;color:#5b6b80;border-top:1px solid #dde3ea}
.ficha{display:grid;grid-template-columns:1fr 1fr;gap:0;border:1px solid #dde3ea;border-radius:4px;overflow:hidden}
.ficha div{padding:8px 12px;border-bottom:1px solid #dde3ea}.ficha div:nth-child(odd){border-right:1px solid #dde3ea}
.ficha span{display:block;font-size:8.5pt;color:#5b6b80;text-transform:uppercase;letter-spacing:.5px}
.ficha b{font-size:11pt}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:10px 0}
.kpi{border:1px solid #dde3ea;border-left:4px solid var(--blue);border-radius:3px;padding:8px 10px}
.kpi b{display:block;font-size:17pt;color:var(--navy);line-height:1.1}.kpi span{font-size:8.5pt;color:#5b6b80}
.kpi.ok{border-left-color:var(--green)}.kpi.ok b{color:var(--green)}
.kpi.al{border-left-color:var(--amber)}.kpi.al b{color:#a86b00}
.kpi.er{border-left-color:var(--red)}.kpi.er b{color:var(--red)}
.concl{list-style:none;padding:0;margin:8px 0}
.concl li{padding:7px 10px 7px 34px;margin:5px 0;background:#F6F8FB;border-radius:3px;position:relative}
.concl li:before{position:absolute;left:10px;top:6px;font-weight:bold}
.concl li.ok:before{content:"✓";color:var(--green)}.concl li.al:before{content:"!";color:#a86b00}
.concl li.er:before{content:"✕";color:var(--red)}
table{width:100%%;border-collapse:collapse;font-size:9.5pt;margin:6px 0}
th{background:var(--blue);color:#fff;font-weight:bold;text-align:left;padding:5px 8px}
td{padding:4px 8px;border-bottom:1px solid #e3e8ee;font-variant-numeric:tabular-nums}
tr:nth-child(even) td{background:#F7F9FC}td.n,th.n{text-align:right}
.st{display:inline-block;padding:0 7px;border-radius:9px;font-size:8.5pt;font-weight:bold;color:#fff}
.st.ok{background:var(--green)}.st.al{background:#C98A00}.st.er{background:var(--red)}
.bar{height:7px;background:var(--blue);border-radius:3px}
svg.graf,svg.mapa{width:100%%;height:auto;display:block}
svg.mapa{border:1px solid #dde3ea;border-radius:4px;background:#FBFCFE}
.grade{stroke:#e3e8ee;stroke-width:1}.eixo{font:10px Arial;fill:#5b6b80}
.val{font:bold 10px Arial;fill:var(--navy)}.rot{font:bold 10px Arial;fill:var(--navy);paint-order:stroke;stroke:#fff;stroke-width:3px}
.leg{display:flex;flex-wrap:wrap;gap:14px;font-size:9pt;color:#5b6b80;margin:4px 0 0 52px}
.leg i{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:5px;vertical-align:-2px}
.quebra{break-before:page}.bloco{break-inside:avoid}
.dois{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.rodape{margin-top:20px;padding-top:6px;border-top:1px solid #dde3ea;font-size:8.5pt;color:#8497B0}
.acoes{max-width:210mm;margin:12px auto 0;text-align:right}
.acoes button{font:bold 10pt Arial;background:var(--navy);color:#fff;border:0;border-radius:4px;padding:8px 14px;cursor:pointer}
@media print{body{background:#fff}.folha{box-shadow:none;margin:0;padding:0;max-width:none}
.capa{min-height:260mm}.acoes{display:none}h1,h2,.kpis,svg,table tr{break-inside:avoid}h1,h2{break-after:avoid}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:640px){.kpis{grid-template-columns:1fr 1fr}.dois,.ficha{grid-template-columns:1fr}.folha{padding:16px}}
""" % (NAVY, AMBER, BLUE, SLATE, RED, GREEN)


def classe_p(pmin, pmax, lim):
    if pmin < lim[0]:
        return "er"
    if pmax > lim[1]:
        return "al"
    return "ok"


def main():
    inp = Inp(arg_arquivo(1, "$INPFILE"))
    # $INPFILE [limites] -> simula;  $INPFILE arquivo.out [limites] -> usa resultados prontos
    def eh_numero(s):
        try:
            float(s.strip("`'\" ").replace(",", ".")); return True
        except ValueError:
            return False
    tem_out = len(sys.argv) > 2 and not eh_numero(sys.argv[2])
    out = SaidaBinaria(resultados_de(arg_arquivo(2, "arquivo de resultados")) if tem_out else simular(inp.caminho))
    pmin_l, pmax_l, vmin_l, vmax_l = numeros(sys.argv[(3 if tem_out else 2):], [10.0, 40.0, 0.4, 3.5])
    kP = CONV_P.get(out.u_pressao, 1.0)
    si = out.u_vazao >= 5
    uv, ul, ud = ("m/s", "m", "mm") if si else ("ft/s", "ft", "pol")
    uq = UNID_VAZAO.get(out.u_vazao, "")
    if not si:
        vmin_l, vmax_l = vmin_l / 0.3048, vmax_l / 0.3048

    spec = importlib.util.spec_from_file_location("verif", os.path.join(AQUI, "02_verificar_consistencia.py"))
    verif = importlib.util.module_from_spec(spec); spec.loader.exec_module(verif)
    achados = verif.verificar(inp)

    fontes = {t[0] for t in inp.tabela("RESERVOIRS")}
    tanques = {t[0] for t in inp.tabela("TANKS")}
    J = [i for i in range(out.nn) if i not in out.idx_fontes]
    T = [j for j in range(out.nl) if out.link_tipo[j] <= 1]
    serie_p = []
    consumo = []
    pmin = {i: (1e9, 0) for i in J}; pmax = {i: (-1e9, 0) for i in J}
    vmax = {j: (0.0, 0) for j in T}
    for k in range(out.nperiodos):
        pr, ve, _, st = out.periodo(k)
        dm = out.demandas(k)
        pk = [pr[i] * kP for i in range(out.nn)]
        serie_p.append(pk)
        consumo.append(sum(dm[i] for i in J))
        for i in J:
            if pk[i] < pmin[i][0]: pmin[i] = (pk[i], k)
            if pk[i] > pmax[i][0]: pmax[i] = (pk[i], k)
        for j in T:
            if st[j] > 2 and abs(ve[j]) > vmax[j][0]:
                vmax[j] = (abs(ve[j]), k)

    nJ, nT = len(J), len(T)
    lim_p = (pmin_l, pmax_l)
    cls = {i: classe_p(pmin[i][0], pmax[i][0], lim_p) for i in J}
    n_ok = sum(1 for c in cls.values() if c == "ok")
    baixa = sorted((i for i in J if pmin[i][0] < pmin_l), key=lambda i: pmin[i][0])
    alta = sorted((i for i in J if pmax[i][0] > pmax_l), key=lambda i: -pmax[i][0])
    rap = sorted((j for j in T if vmax[j][0] > vmax_l), key=lambda j: -vmax[j][0])
    lenta = [j for j in T if vmax[j][0] < vmin_l]
    ne = sum(1 for a in achados if a[0] == "erro"); na = len(achados) - ne
    imin = min(J, key=lambda i: pmin[i][0]); imax = max(J, key=lambda i: pmax[i][0])

    # dados de cadastro
    tubos = inp.tabela("PIPES")
    ext = sum(float(t[3]) for t in tubos)
    por_d = {}
    for t in tubos:
        d = float(t[4]); por_d.setdefault(d, [0, 0.0]); por_d[d][0] += 1; por_d[d][1] += float(t[3])
    titulo = " ".join(inp.tabela("TITLE")[0]) if inp.tabela("TITLE") else os.path.splitext(os.path.basename(inp.caminho))[0]
    dur_h = out.duracao / 3600
    hoje = datetime.date.today().strftime("%d/%m/%Y")

    # ---------- CAPA
    h = ["<div class='acoes'><button onclick='print()'>Imprimir / salvar PDF</button></div>"]
    h.append("<section class='folha capa'><div class='topo'>%s<div class='sup'>IARHA · DIAGNÓSTICO HIDRÁULICO</div>"
             "<p class='tit'>Relatório de Diagnóstico<br>da Rede de Distribuição</p><div class='proj'>%s</div></div>"
             % (logo_html(92), esc(titulo)))
    h.append("<div class='meio'><div class='ficha'>")
    for rot, val in [("Arquivo do modelo", os.path.basename(inp.caminho)), ("Data", hoje),
                     ("Unidade de vazão", uq), ("Fórmula de perda de carga", inp.formula()),
                     ("Período simulado", "%s h (%d períodos)" % (fmt(dur_h, 0), out.nperiodos)),
                     ("Critério de pressão", "%s a %s mca" % (fmt(pmin_l, 0), fmt(pmax_l, 0))),
                     ("Critério de velocidade", "%s a %s %s" % (fmt(vmin_l, 1), fmt(vmax_l, 1), uv)),
                     ("Referência normativa", "ABNT NBR 12218")]:
        h.append("<div><span>%s</span><b>%s</b></div>" % (esc(rot), esc(val)))
    h.append("</div><h2>Situação geral</h2><div class='kpis'>")
    kp = lambda c, v, r: "<div class='kpi %s'><b>%s</b><span>%s</span></div>" % (c, v, esc(r))
    h.append(kp("ok" if n_ok == nJ else ("al" if n_ok >= 0.9 * nJ else "er"),
                fmt(100 * n_ok / max(nJ, 1), 0) + "%", "nós dentro da faixa de pressão"))
    h.append(kp("er" if baixa else "ok", len(baixa), "nós com pressão mínima baixa"))
    h.append(kp("al" if alta else "ok", len(alta), "nós com pressão máxima alta"))
    h.append(kp("er" if ne else ("al" if na else "ok"), ne + na, "inconsistências de cadastro"))
    h.append("</div></div><div class='rod'>Simulação hidráulica executada pelo EPANET 2.2 (USEPA · versão brasileira LENHS/UFPB). "
             "Relatório gerado automaticamente pela ferramenta IARHA em %s.</div></section>" % hoje)

    # ---------- 1 SÍNTESE
    h.append("<section class='folha'><h1><b>1</b>Síntese do diagnóstico</h1><ul class='concl'>")
    c = "ok" if n_ok == nJ else ("al" if n_ok >= 0.9 * nJ else "er")
    h.append("<li class='%s'><b>%d de %d nós (%s%%)</b> permanecem entre %s e %s mca durante todo o período simulado.</li>"
             % (c, n_ok, nJ, fmt(100 * n_ok / max(nJ, 1), 1), fmt(pmin_l, 0), fmt(pmax_l, 0)))
    if baixa:
        h.append("<li class='er'>Pressão mínima da rede: <b>%s mca no nó %s às %s</b>, abaixo do mínimo dinâmico. "
                 "%d nó(s) ficam abaixo de %s mca em algum instante.</li>"
                 % (fmt(pmin[imin][0], 1), esc(out.nos[imin]), out.hora(pmin[imin][1]), len(baixa), fmt(pmin_l, 0)))
    else:
        h.append("<li class='ok'>Nenhum nó fica abaixo de %s mca; mínima de %s mca no nó %s.</li>"
                 % (fmt(pmin_l, 0), fmt(pmin[imin][0], 1), esc(out.nos[imin])))
    if alta:
        h.append("<li class='al'>Pressão máxima: <b>%s mca no nó %s às %s</b>. %d nó(s) ultrapassam %s mca — "
                 "avaliar setorização ou controle de pressão nessas áreas.</li>"
                 % (fmt(pmax[imax][0], 1), esc(out.nos[imax]), out.hora(pmax[imax][1]), len(alta), fmt(pmax_l, 0)))
    else:
        h.append("<li class='ok'>Nenhum nó ultrapassa %s mca.</li>" % fmt(pmax_l, 0))
    if rap:
        h.append("<li class='er'>%d trecho(s) superam %s %s; máximo de %s %s no trecho %s.</li>"
                 % (len(rap), fmt(vmax_l, 1), uv, fmt(vmax[rap[0]][0], 2), uv, esc(out.links[rap[0]])))
    else:
        h.append("<li class='ok'>Nenhum trecho supera %s %s.</li>" % (fmt(vmax_l, 1), uv))
    if lenta:
        h.append("<li class='al'>%d trecho(s) não atingem %s %s em nenhum instante — possível superdimensionamento "
                 "ou estagnação.</li>" % (len(lenta), fmt(vmin_l, 1), uv))
    h.append("<li class='%s'>Verificação do cadastro: <b>%d erro(s)</b> e <b>%d aviso(s)</b>.</li>"
             % ("er" if ne else ("al" if na else "ok"), ne, na))
    h.append("</ul>")

    # ---------- 2 CARACTERIZAÇÃO
    h.append("<h1><b>2</b>Caracterização da rede</h1><div class='kpis'>")
    h.append(kp("", nJ, "nós de consumo"))
    h.append(kp("", len(fontes) + len(tanques), "reservatórios"))
    h.append(kp("", len(tubos), "tubulações"))
    h.append(kp("", fmt(ext / 1000, 2) + " km" if si else fmt(ext, 0) + " ft", "extensão total"))
    h.append("</div><div class='kpis'>")
    h.append(kp("", len(inp.tabela("PUMPS")), "bombas"))
    h.append(kp("", len(inp.tabela("VALVES")), "válvulas"))
    h.append(kp("", fmt(max(consumo), 1) + " " + uq, "consumo máximo"))
    h.append(kp("", fmt(sum(consumo) / len(consumo), 1) + " " + uq, "consumo médio"))
    h.append("</div><h2>Extensão por diâmetro</h2><table><tr><th>Diâmetro (%s)</th><th class='n'>Trechos</th>"
             "<th class='n'>Extensão (%s)</th><th class='n'>%%</th><th style='width:35%%'></th></tr>" % (ud, ul))
    mx = max(v[1] for v in por_d.values())
    for d in sorted(por_d):
        n, L = por_d[d]
        h.append("<tr><td>%s</td><td class='n'>%d</td><td class='n'>%s</td><td class='n'>%s</td>"
                 "<td><div class='bar' style='width:%.0f%%'></div></td></tr>"
                 % (fmt(d, 0 if si else 1), n, fmt(L, 1), fmt(100 * L / ext, 1), 100 * L / mx))
    h.append("</table>")
    estatica = out.nperiodos < 2
    if not estatica:
        h.append("<h2>Consumo total ao longo do período</h2>")
        h.append(svg_linhas([("Consumo total (%s)" % uq, BLUE, consumo)], [out.hora(k) for k in range(out.nperiodos)], uq, alt=220))
    h.append("</section>")

    # ---------- 3 MAPA
    cor_no = {out.nos[i]: {"ok": GREEN, "al": AMBER, "er": RED}[cls[i]] for i in J}
    cor_lk = {}
    if tubos:
        dmax = max(float(t[4]) for t in tubos) or 1
    for j in range(out.nl):
        if j in vmax and tubos:   # tubo: espessura pelo diâmetro, limitada
            w = 1.5 + 3.5 * min(max(out.diametros[j] / dmax, 0.0), 1.0)
        else:                      # bomba/válvula: espessura fixa (diâmetro não é confiável)
            w = 2.5
        if j in vmax:
            cor = RED if vmax[j][0] > vmax_l else (SLATE if vmax[j][0] < vmin_l else BLUE)
        else:
            cor = NAVY
        cor_lk[out.links[j]] = (cor, w)
    destaque = [out.nos[i] for i in (baixa + alta)[:(25 if nJ < 300 else 10)]]
    h.append("<section class='folha'><h1><b>3</b>Mapa de pressões</h1>")
    h.append("<p>Cada nó recebe a pior condição do período simulado. Espessura dos trechos proporcional ao diâmetro; "
             "cor pela velocidade máxima.</p>")
    h.append("<div class='bloco'>" + svg_mapa(inp, cor_no, cor_lk, destaque, fontes, tanques))
    h.append("<div class='leg' style='margin-left:0;margin-top:6px'>"
             "<span><i style='background:%s'></i>Pressão dentro da faixa</span>"
             "<span><i style='background:%s'></i>Pmáx &gt; %s mca</span>"
             "<span><i style='background:%s'></i>Pmín &lt; %s mca</span>"
             "<span><i style='background:%s'></i>V na faixa</span>"
             "<span><i style='background:%s'></i>V &lt; %s %s</span>"
             "<span><i style='background:%s'></i>V &gt; %s %s</span>"
             "<span><i style='background:%s'></i>Reservatório (RNF)</span>"
             "<span><i style='background:%s;outline:1.5px solid %s'></i>Tanque (RNV)</span>"
             "<span><i style='background:repeating-linear-gradient(90deg,%s 0 5px,transparent 5px 8px)'></i>Bomba / válvula</span></div>"
             % (GREEN, AMBER, fmt(pmax_l, 0), RED, fmt(pmin_l, 0), BLUE, SLATE, fmt(vmin_l, 1), uv,
                RED, fmt(vmax_l, 1), uv, NAVY, AMBER, NAVY, NAVY) + "</div>")

    # ---------- 4 PRESSÕES
    h.append("<h1 style='margin-top:22px'><b>4</b>Pressões</h1><h2>Distribuição das pressões mínimas</h2>")
    amp = max(pmin[i][0] for i in J) - min(0, min(pmin[i][0] for i in J))
    faixa = next((f for f in (5, 10, 20, 25, 50, 100) if amp / f <= 16), 200)
    topo = int(max(pmin[i][0] for i in J) // faixa + 1)
    base = int(min(0, min(pmin[i][0] for i in J)) // faixa)
    rot, val, cores = [], [], []
    for b in range(base, topo):
        a = b * faixa
        rot.append("%d–%d" % (a, a + faixa))
        val.append(sum(1 for i in J if a <= pmin[i][0] < a + faixa))
        cores.append(RED if a + faixa <= pmin_l else (AMBER if a >= pmax_l else BLUE))
    h.append(svg_barras(rot, val, cores, "nós"))
    criticos = (baixa[:3] + alta[:1]) or sorted(J, key=lambda i: pmin[i][0])[:3]
    paleta = [RED, "#E67E22", NAVY, AMBER, BLUE]
    if estatica:
        h.append("<p class='nota'>Simulação estática (um único período): gráficos temporais não se aplicam.</p>")
    else:
        h.append("<h2>Pressão nos nós críticos ao longo do período</h2>")
    h.append("" if estatica else svg_linhas([("Nó %s" % out.nos[i], paleta[n % 5], [serie_p[k][i] for k in range(out.nperiodos)])
                         for n, i in enumerate(criticos)],
                        [out.hora(k) for k in range(out.nperiodos)], "pressão (mca)",
                        faixas=[(pmin_l, pmax_l, GREEN, .08)]))
    if not estatica:
        h.append("<p class='nota'>Faixa verde: intervalo de pressão admissível (%s–%s mca).</p>" % (fmt(pmin_l, 0), fmt(pmax_l, 0)))
    if baixa or alta:
        h.append("<h2>Nós fora da faixa</h2><table><tr><th>Nó</th><th class='n'>Pmín (mca)</th><th>Hora</th>"
                 "<th class='n'>Pmáx (mca)</th><th>Hora</th><th>Situação</th></tr>")
        for i in (baixa + alta)[:60]:
            c = cls[i]
            h.append("<tr><td><b>%s</b></td><td class='n'>%s</td><td>%s</td><td class='n'>%s</td><td>%s</td>"
                     "<td><span class='st %s'>%s</span></td></tr>"
                     % (esc(out.nos[i]), fmt(pmin[i][0], 2), out.hora(pmin[i][1]), fmt(pmax[i][0], 2),
                        out.hora(pmax[i][1]), c, {"er": "pressão baixa", "al": "pressão alta"}[c]))
        h.append("</table>")
    h.append("</section>")

    # ---------- 5 VELOCIDADES + 6 CONSISTÊNCIA
    h.append("<section class='folha'><h1><b>5</b>Velocidades</h1>")
    faixas_v = [0, .2, .4, .6, 1.0, 1.5, 2.0, 3.5, 99] if si else [0, .65, 1.3, 2, 3.3, 5, 6.5, 11.5, 999]
    rot, val, cores = [], [], []
    for a, b in zip(faixas_v, faixas_v[1:]):
        rot.append(("> %s" % fmt(a, 1)) if b >= 99 else "%s–%s" % (fmt(a, 1), fmt(b, 1)))
        val.append(sum(1 for j in T if a <= vmax[j][0] < b))
        cores.append(SLATE if b <= vmin_l + 1e-9 else (RED if a >= vmax_l - 1e-9 else BLUE))
    h.append("<h2>Distribuição das velocidades máximas (%s)</h2>" % uv)
    h.append(svg_barras(rot, val, cores, "trechos"))
    if rap or lenta:
        h.append("<h2>Trechos fora da faixa</h2><table><tr><th>Trecho</th><th class='n'>DN (%s)</th>"
                 "<th class='n'>Vmáx (%s)</th><th>Hora</th><th>Situação</th></tr>" % (ud, uv))
        for j in (rap + sorted(lenta, key=lambda j: vmax[j][0]))[:40]:
            alta_v = vmax[j][0] > vmax_l
            h.append("<tr><td><b>%s</b></td><td class='n'>%s</td><td class='n'>%s</td><td>%s</td>"
                     "<td><span class='st %s'>%s</span></td></tr>"
                     % (esc(out.links[j]), fmt(out.diametros[j], 0), fmt(vmax[j][0], 2), out.hora(vmax[j][1]),
                        "er" if alta_v else "al", "velocidade alta" if alta_v else "velocidade baixa"))
        h.append("</table>")
    h.append("<h1 style='margin-top:22px'><b>6</b>Consistência do modelo</h1>")
    if achados:
        h.append("<table><tr><th>Gravidade</th><th>Categoria</th><th>Objeto</th><th>Detalhe</th></tr>")
        for g, cat, o, d in achados[:80]:
            h.append("<tr><td><span class='st %s'>%s</span></td><td>%s</td><td><b>%s</b></td><td>%s</td></tr>"
                     % ("er" if g == "erro" else "al", g, esc(cat), esc(o), esc(d)))
        h.append("</table>")
    else:
        h.append("<ul class='concl'><li class='ok'>Nenhuma inconsistência encontrada: IDs, conectividade, comprimentos, "
                 "diâmetros, rugosidades, cotas e coordenadas verificados.</li></ul>")
    h.append("</section>")

    # ---------- ANEXO
    h.append("<section class='folha quebra'><h1><b>A</b>Anexo — pressões por nó</h1>"
             "<table><tr><th>Nó</th><th class='n'>Cota (%s)</th><th class='n'>Pmín (mca)</th><th>Hora</th>"
             "<th class='n'>Pmáx (mca)</th><th>Hora</th><th>Situação</th></tr>" % ul)
    for i in J[:400]:
        c = cls[i]
        h.append("<tr><td>%s</td><td class='n'>%s</td><td class='n'>%s</td><td>%s</td><td class='n'>%s</td><td>%s</td>"
                 "<td><span class='st %s'>%s</span></td></tr>"
                 % (esc(out.nos[i]), fmt(out.cotas[i], 1), fmt(pmin[i][0], 2), out.hora(pmin[i][1]),
                    fmt(pmax[i][0], 2), out.hora(pmax[i][1]), c, {"ok": "ok", "er": "baixa", "al": "alta"}[c]))
    h.append("</table>")
    if nJ > 400:
        h.append("<p class='nota'>Mostrando 400 de %d nós.</p>" % nJ)
    h.append("<div class='rodape'>Os resultados refletem o modelo e os dados de entrada fornecidos; a calibração "
             "e a validação de campo são responsabilidade do projetista. Pressão máxima simulada usada como "
             "aproximação da pressão estática.</div></section>")

    caminho = gravar_relatorio_iarha("Diagnóstico Hidráulico — " + titulo, "".join(h))
    return caminho


def gravar_relatorio_iarha(titulo, corpo):
    import tempfile, webbrowser, re
    # 1ª linha de cada tabela vira <thead>, repetido no topo de cada página impressa
    corpo = re.sub(r"<table><tr>(.*?)</tr>", r"<table><thead><tr>\1</tr></thead><tbody>", corpo)
    corpo = corpo.replace("</table>", "</tbody></table>")
    pasta = tempfile.gettempdir()
    caminho = os.path.join(pasta, "IARHA_Diagnostico_Hidraulico.html")
    doc = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
           "<meta name='viewport' content='width=device-width,initial-scale=1'><title>%s</title>"
           "<style>%s</style></head><body>%s</body></html>") % (esc(titulo), CSS_REL, corpo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(doc)
    webbrowser.open("file:///" + caminho.replace("\\", "/"))
    return caminho


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        avisar("Relatório IARHA — erro", "%s\n\n%s" % (e, traceback.format_exc()[-600:]), erro=True)
